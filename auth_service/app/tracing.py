from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry import trace
import os

def setup_tracing(app, service_name: str):
    # 1. Створення Resource (для ідентифікації сервісу в Jaeger)
    # Це важливо для коректного відображення в Jaeger UI
    resource = Resource.create({
        "service.name": service_name,
        "environment": os.getenv("ENVIRONMENT", "local"),
    })

    # 2. Налаштування провайдера трасування
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # 3. Налаштування Експортера (відправляє дані трасування)
    # Jaeger всередині Docker мережі доступний за іменем jaeger:4318
    exporter = OTLPSpanExporter(
        endpoint="http://jaeger:4318/v1/traces" 
    )

    # 4. Процесор (асинхронно відправляє траси, не блокуючи роботу застосунку)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # 5. Автоматичне інструментування FastAPI та HTTP-запитів
    # Автоматично створює span для кожного вхідного запиту.
    FastAPIInstrumentor.instrument_app(app) 
    
    # Автоматично створює span для вихідних requests.get(), requests.post() тощо.
    # Це дозволяє передавати ідентифікатори трасування від одного сервісу до іншого.
    RequestsInstrumentor().instrument()