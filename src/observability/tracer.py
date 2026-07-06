# OpenTelemetry Telemetry Tracer Instrumentation
# Owner: YOU (Lead)

import sys
import inspect
import functools
# Reconfigure stdout/stderr to UTF-8 for Windows console support
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except (AttributeError, IOError):
    pass
from typing import Callable, Any, Dict, List
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# Try to initialize a console exporter for local debugging if no global tracer provider is configured
try:
    # Check if the current provider is just a proxy (not yet initialized by ADK)
    if "ProxyTracerProvider" in type(trace.get_tracer_provider()).__name__:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
        
        provider = TracerProvider()
        # Use SimpleSpanProcessor to print trace spans immediately to the console for verification
        processor = SimpleSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        print("[OTEL TRACER] Initialized local ConsoleSpanExporter for debugging.")
except Exception as e:
    # Fail silently if already initialized by ADK runtime to prevent collisions
    pass

# Get or create OpenTelemetry tracer for the safety agent
tracer = trace.get_tracer("clean-label-agent")

def trace_span(span_name: str):
    """
    A decorator to instrument a function with an OpenTelemetry trace span.
    It starts a span, executes the decorated function, handles any exceptions,
    sets span statuses, and records key metadata attributes (Day 4 Concept).
    
    Supports both standard functions and async generator functions (HIL checkpoints).
    
    Args:
        span_name (str): Name of the span (e.g. perceive, plan, query_databases).
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if inspect.isasyncgenfunction(func):
            @functools.wraps(func)
            async def async_gen_wrapper(*args: Any, **kwargs: Any) -> Any:
                with tracer.start_as_current_span(span_name) as span:
                    print(f"[OTEL SPAN START] Entering async generator stage: {span_name}")
                    try:
                        async for item in func(*args, **kwargs):
                            # Record metadata on yielded events if available
                            if item is not None and hasattr(item, "state") and item.state:
                                state = item.state
                                if "product_name" in state:
                                    span.set_attribute("agent.product_name", str(state["product_name"]))
                                if "category" in state:
                                    span.set_attribute("agent.category", str(state["category"]))
                                if "verdict" in state:
                                    span.set_attribute("agent.verdict", str(state["verdict"]))
                            yield item
                        span.set_status(Status(StatusCode.OK))
                        print(f"[OTEL SPAN SUCCESS] Exiting async generator stage: {span_name}")
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, description=str(e)))
                        print(f"[OTEL SPAN ERROR] Async generator stage: {span_name} failed: {e}")
                        raise e
            return async_gen_wrapper
        elif inspect.isgeneratorfunction(func):
            @functools.wraps(func)
            def sync_gen_wrapper(*args: Any, **kwargs: Any) -> Any:
                with tracer.start_as_current_span(span_name) as span:
                    print(f"[OTEL SPAN START] Entering generator stage: {span_name}")
                    try:
                        for item in func(*args, **kwargs):
                            # Record metadata on yielded events if available
                            if item is not None and hasattr(item, "state") and item.state:
                                state = item.state
                                if "product_name" in state:
                                    span.set_attribute("agent.product_name", str(state["product_name"]))
                                if "category" in state:
                                    span.set_attribute("agent.category", str(state["category"]))
                                if "verdict" in state:
                                    span.set_attribute("agent.verdict", str(state["verdict"]))
                            yield item
                        span.set_status(Status(StatusCode.OK))
                        print(f"[OTEL SPAN SUCCESS] Exiting generator stage: {span_name}")
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, description=str(e)))
                        print(f"[OTEL SPAN ERROR] Generator stage: {span_name} failed: {e}")
                        raise e
            return sync_gen_wrapper
        elif inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with tracer.start_as_current_span(span_name) as span:
                    print(f"[OTEL SPAN START] Entering async stage: {span_name}")
                    try:
                        result = await func(*args, **kwargs)
                        if result is not None:
                            if hasattr(result, "state") and result.state:
                                state = result.state
                                if "product_name" in state:
                                    span.set_attribute("agent.product_name", str(state["product_name"]))
                                if "category" in state:
                                    span.set_attribute("agent.category", str(state["category"]))
                                if "verdict" in state:
                                    span.set_attribute("agent.verdict", str(state["verdict"]))
                        span.set_status(Status(StatusCode.OK))
                        print(f"[OTEL SPAN SUCCESS] Exiting async stage: {span_name}")
                        return result
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, description=str(e)))
                        print(f"[OTEL SPAN ERROR] Async stage: {span_name} failed: {e}")
                        raise e
            return async_wrapper
        else:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Start a named trace span using the OpenTelemetry tracer
                with tracer.start_as_current_span(span_name) as span:
                    print(f"[OTEL SPAN START] Entering stage: {span_name}")
                    try:
                        result = func(*args, **kwargs)
                        
                        # Record metadata attributes to the span if available
                        # Inspect result to extract parameters (confidence, sources, category)
                        if result is not None:
                            # Extracting from Event state deltas
                            if hasattr(result, "state") and result.state:
                                state = result.state
                                if "product_name" in state:
                                    span.set_attribute("agent.product_name", str(state["product_name"]))
                                if "category" in state:
                                    span.set_attribute("agent.category", str(state["category"]))
                                if "raw_mcp_data" in state:
                                    db = state["raw_mcp_data"].get("database", "Unknown")
                                    span.set_attribute("agent.database_source", db)
                                if "verdict" in state:
                                    span.set_attribute("agent.verdict", str(state["verdict"]))
                                if "attempt" in state:
                                    span.set_attribute("agent.loop_attempt", int(state["attempt"]))
                                    
                        span.set_status(Status(StatusCode.OK))
                        print(f"[OTEL SPAN SUCCESS] Exiting stage: {span_name}")
                        return result
                    except Exception as e:
                        # Record the exception details in the trace span
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, description=str(e)))
                        print(f"[OTEL SPAN ERROR] Stage: {span_name} failed: {e}")
                        raise e
            return wrapper
    return decorator
