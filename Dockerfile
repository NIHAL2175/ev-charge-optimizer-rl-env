FROM python:3.10-slim


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH


RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*


RUN useradd -m -u 1000 user


WORKDIR $HOME/app


COPY --chown=user requirements.txt .


RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


USER user


COPY --chown=user . .


EXPOSE 7860

CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "7860"]
