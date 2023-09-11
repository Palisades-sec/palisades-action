FROM python:3.10-slim-bullseye
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH /app
CMD ["main.py"]

# FROM python:3.10-slim-bullseye AS builder
# WORKDIR /app
# COPY . /app
# # We are installing a dependency here directly into our app source dir
# RUN pip install --target=/app --no-cache-dir -r requirements.txt

# # A distroless container image with Python and some basics like SSL certificates
# # https://github.com/GoogleContainerTools/distroless
# FROM gcr.io/distroless/python3-debian11
# COPY --from=builder /app /app
# WORKDIR /app
# ENV PYTHONPATH /app
# CMD ["/app/main.py"]
