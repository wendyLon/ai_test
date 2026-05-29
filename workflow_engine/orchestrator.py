"""Central orchestrator that consumes incoming tasks and drives the workflow state machine.

Expect incoming tasks pushed to `orchestrator:input` (Redis list) as JSON messages with fields:
- `url` or provider-specific payload
- `workflow` (optional): name of workflow to use

Agents should post their step results to `orchestrator:results` as JSON with `task_id`, `trace_id`, `step`, `status`, `result`.
"""
import asyncio
import json
import time
import uuid
from typing import Dict, Any
from platform.redis_client import get_redis_client
from platform.queue_manager import QueueManager
from workflow_engine.state_machine import StateMachine, State
from workflow_engine.workflow_definitions import load_workflow_from_yaml
from workflow_engine.execution_graph import ExecutionGraph
from platform.observability.otel import get_tracer, inject_trace_into_message


class Orchestrator:
    def __init__(self, namespace: str = 'sen', input_queue: str = 'orchestrator:input', result_queue: str = 'orchestrator:results'):
        self.ns = namespace
        self.r = get_redis_client()
        self.qm = QueueManager(namespace)
        self.input_queue = input_queue
        self.result_queue = result_queue
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self.graphs: Dict[str, ExecutionGraph] = {}

    def load_workflow(self, name: str, path: str):
        wf = load_workflow_from_yaml(path)
        self.workflows[name] = wf
        self.graphs[name] = ExecutionGraph(wf['steps'], wf.get('config'))

    async def _consume_incoming(self):
        # BRPOP from input_queue
        while True:
            try:
                item = self.r.blpop(self.input_queue, timeout=5)
                if not item:
                    await asyncio.sleep(0.1)
                    continue
                _, raw = item
                msg = json.loads(raw)
                await self._handle_new_task(msg)
            except Exception:
                await asyncio.sleep(1)

    async def _consume_results(self):
        while True:
            try:
                item = self.r.blpop(self.result_queue, timeout=5)
                if not item:
                    await asyncio.sleep(0.1)
                    continue
                _, raw = item
                msg = json.loads(raw)
                await self._handle_result(msg)
            except Exception:
                await asyncio.sleep(1)

    async def _handle_new_task(self, msg: Dict[str, Any]):
        # create state machine
        task_id = msg.get('task_id') or str(uuid.uuid4())
        sm = StateMachine(task_id=task_id, namespace=self.ns)
        # attach trace id to top-level task metadata
        trace_id = sm.trace_id
        wf_name = msg.get('workflow') or 'sen_training_pipeline'
        wf = self.workflows.get(wf_name)
        if not wf:
            # try default path
            self.load_workflow(wf_name, f'workflows/{wf_name}.yaml')
            wf = self.workflows.get(wf_name)
        graph = self.graphs.get(wf_name)
        # dispatch first step
        first = wf['steps'][0]
        payload = {
            'task_id': task_id,
            'trace_id': trace_id,
            'step': first,
            'payload': msg.get('payload') or msg,
            'workflow': wf_name,
        }
        # inject trace into message
        inject_trace_into_message(payload)
        # determine agent queue name convention: <step>-worker
        agent_queue = f"{first}-worker"
        self.qm.push(agent_queue, payload)
        sm.transition_to(State.DISCOVERED, agent_result=None, meta={'dispatched_to': agent_queue})

    async def _handle_result(self, msg: Dict[str, Any]):
        # expected fields: task_id, trace_id, step, status, result
        task_id = msg.get('task_id')
        trace_id = msg.get('trace_id')
        step = msg.get('step')
        status = msg.get('status')
        result = msg.get('result')
        # load state machine transitions by trace_id -> find task_id via task hash
        # reconstruct minimal state machine
        sm = StateMachine(task_id=task_id, namespace=self.ns)
        sm.trace_id = trace_id
        sm._transitions_key = f"{self.ns}:trace:{trace_id}:transitions"
        sm._task_key = f"{self.ns}:task:{task_id}"
        # record step result
        if status == 'ok':
            # map step to next state
            step_state_map = {
                'discovery': State.DISCOVERED,
                'crawl': State.CRAWLED,
                'dom_analysis': State.DOM_ANALYZING,
                'extract': State.EXTRACTING,
                'sen_classify': State.CLASSIFYING_SEN,
                'dedup': State.DEDUPING,
                'sql': State.SQL_EXPORTING,
            }
            next_state = step_state_map.get(step, None)
            if next_state:
                sm.transition_to(next_state, agent_result=result, meta={'step': step})
            # decide next nodes via graph
            wf_name = msg.get('workflow') or 'sen_training_pipeline'
            graph = self.graphs.get(wf_name)
            if not graph:
                try:
                    self.load_workflow(wf_name, f'workflows/{wf_name}.yaml')
                    graph = self.graphs.get(wf_name)
                except Exception:
                    graph = None
            next_nodes = []
            if graph:
                next_nodes = graph.get_next(step, {'result': result})
            if not next_nodes:
                # if no next, consider completed
                sm.transition_to(State.COMPLETED, agent_result=result, meta={'step': step})
                return
            for n in next_nodes:
                payload = {'task_id': task_id, 'trace_id': trace_id, 'step': n, 'payload': result, 'workflow': wf_name}
                inject_trace_into_message(payload)
                agent_queue = f"{n}-worker"
                self.qm.push(agent_queue, payload)
        else:
            # failure handling: increment retry and route
            sm.transition_to(State.RETRYING, agent_result={'step': step, 'error': result}, meta={'step': step})
            # check retry count
            rc = sm.increment_retry(State.RETRYING)
            policy = 3
            if rc > policy:
                sm.transition_to(State.DEAD_LETTER, agent_result={'step': step}, meta={'reason': 'max_retries'})
            else:
                # requeue same step after backoff
                delay = 2 ** (rc - 1)
                await asyncio.sleep(delay)
                payload = {'task_id': task_id, 'trace_id': trace_id, 'step': step, 'payload': msg.get('result'), 'workflow': msg.get('workflow')}
                inject_trace_into_message(payload)
                agent_queue = f"{step}-worker"
                self.qm.push(agent_queue, payload)

    async def run(self):
        t1 = asyncio.create_task(self._consume_incoming())
        t2 = asyncio.create_task(self._consume_results())
        await asyncio.gather(t1, t2)


def main():
    import asyncio
    o = Orchestrator()
    # pre-load default workflow path
    try:
        o.load_workflow('sen_training_pipeline', 'workflows/sen_training_pipeline.yaml')
    except Exception:
        pass
    asyncio.run(o.run())


if __name__ == '__main__':
    main()
