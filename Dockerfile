FROM python:3.12-alpine
RUN apk add --no-cache wireless-tools iw iputils
RUN pip install flask speedtest-cli --no-cache-dir
WORKDIR /app
COPY app.py index.html ./
CMD ["python", "app.py"]
