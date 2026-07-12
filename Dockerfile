FROM python:3.12-alpine
RUN apk add --no-cache wireless-tools iw iputils iproute2
RUN pip install flask speedtest-cli --no-cache-dir
WORKDIR /app
COPY app.py index.html ./
EXPOSE 5000
CMD ["python", "app.py"]
