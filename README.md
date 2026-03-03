# Installation Guide for ConsentGuard

## 1. How to Install Python
- Go to the official [Python website](https://www.python.org/downloads/).
- Download the latest version of Python suitable for your operating system.
- Follow the installation instructions provided on the site.

## 2. How to Create a Virtual Environment
- Open your command line interface (CLI).
- Navigate to the root directory of the project:
  ```bash
  cd ConsentGuard
  ```
- Create a virtual environment with the following command:
  ```bash
  python3 -m venv venv
  ```

## 3. How to Activate the Virtual Environment
- On Windows:
  ```bash
  venv\Scripts\activate
  ```
- On macOS and Linux:
  ```bash
  source venv/bin/activate
  ```

## 4. How to Install Requirements
- Once the virtual environment is activated, run the following command to install the required packages:
  ```bash
  pip install -r requirements.txt
  ```

## 5. How to Run the App
- With the virtual environment activated, navigate to the root of the project (where the app.py file is located) and execute:
  ```bash
  streamlit run app.py
  ```
