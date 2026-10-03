web: cd core && sh -c 'exec gunicorn core.asgi:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000}'
