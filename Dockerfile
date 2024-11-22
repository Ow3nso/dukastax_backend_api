FROM python:3.10.12

# Set the working directory inside the container
WORKDIR /backend

# Copy the requirements file from the backend directory to the container
COPY /requirements.txt .

# Install Python dependencies
RUN pip3 install -r requirements.txt

# Copy the rest of the application code into the container
COPY / .

# Install Gunicorn
RUN pip3 install gunicorn


# Run the application with Gunicorn
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:8000", "backend_payment_apis.wsgi:application"]
