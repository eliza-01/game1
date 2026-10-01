FROM python:3.14-slim
WORKDIR /app
COPY web_server.py /app/web_server.py
COPY static /app/static
EXPOSE 8080
CMD ["python","/app/web_server.py"]
