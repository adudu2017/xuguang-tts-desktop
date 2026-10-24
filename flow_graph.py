"""Validated exact-operation CUDA graph for Ming's deterministic CFM block."""
import inspect
import torch

class GraphFailure(RuntimeError):
    pass

class FlowGraph:
    def __init__(self, cfm):
        self.original = cfm.sample
        self.signature = inspect.signature(self.original)
        self.cache = {}
        self.enabled = True
        self.hits = 0
        # Keep timestep tensors alive; avoid host->device constant creation in capture.
        import fm.CFM as module
        old = module.get_epss_timesteps
        constants = {}
        def timesteps(n, device, dtype):
            if not self.enabled: return old(n, device, dtype)
            key = (n, str(device), dtype)
            if key not in constants: constants[key] = old(n, device, dtype)
            return constants[key]
        module.get_epss_timesteps = timesteps
        self.constants = constants
        cfm.sample = self.call

    def call(self, *args, **kwargs):
        if not self.enabled: return self.original(*args, **kwargs)
        try:
            return self.accelerated(*args, **kwargs)
        except Exception as error:
            raise GraphFailure('CUDA_GRAPH_FAILED: ' + str(error)) from error

    def accelerated(self, *args, **kwargs):
        bound = self.signature.bind(*args, **kwargs); bound.apply_defaults()
        values = bound.arguments
        if not values['noise'].is_cuda: return self.original(*args, **kwargs)
        key = tuple((k, (tuple(v.shape),v.dtype,str(v.device),tuple(v.stride())) if isinstance(v,torch.Tensor) else v) for k,v in values.items())
        if key not in self.cache:
            if len(self.cache)>=2: return self.original(*args, **kwargs)
            static={k:v.clone() if isinstance(v,torch.Tensor) else v for k,v in values.items()}
            stream=torch.cuda.Stream(); stream.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(stream):
                for _ in range(3): expected=self.original(**static)
            torch.cuda.current_stream().wait_stream(stream)
            torch.cuda.synchronize()
            graph=torch.cuda.CUDAGraph()
            with torch.cuda.graph(graph,stream=stream): output=self.original(**static)
            graph.replay();torch.cuda.synchronize()
            if not torch.equal(expected,output): raise RuntimeError('CFM graph output differs from eager output')
            self.cache[key]=(static,graph,output)
        static,graph,output=self.cache[key]
        for k,v in values.items():
            if isinstance(v,torch.Tensor):static[k].copy_(v)
        graph.replay();self.hits+=1
        return output.clone()
