FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY generate_logs.py clean_logs.py pipeline.py ./
CMD ["python", "pipeline.py"]