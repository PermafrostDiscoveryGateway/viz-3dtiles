FROM python:3.9-slim

# Install transitive dependencies
RUN apt-get update \
 && apt-get install -y \
    git \
    libgl1 \
    libgomp1

# Install from source
WORKDIR /app
ADD . .
RUN pip install .


CMD ["python3"]
