FROM python:3.12

WORKDIR /bot

COPY requirements.txt .

RUN pip install -U pip
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8000"]
