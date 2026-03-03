# ConsentGuard

## Setup Instructions

To set up the ConsentGuard project, follow these steps:

### Prerequisites
- Ensure you have Python installed on your system. You can download it from the [official Python website](https://www.python.org/downloads/).

### Installing Python
- **Windows:** Download the executable installer, run it, and make sure to check the box that says `Add Python to PATH`.
- **macOS:** You can use Homebrew by running `brew install python` in your terminal.
- **Linux:** Use your package manager to install Python. For example:
  ```bash
  sudo apt update
  sudo apt install python3
  ```

### Setting Up a Virtual Environment
It is highly recommended to use a virtual environment to manage dependencies.

1. Navigate to your project directory:
    ```bash
    cd path/to/ConsentGuard
    ```
2. Create a virtual environment:
    ```bash
    python -m venv venv
    ```
3. Activate the virtual environment:
   - **Windows:**
        ```bash
        venv\Scripts\activate
        ```
   - **macOS/Linux:**
        ```bash
        source venv/bin/activate
        ```

### Installing Dependencies
Once the virtual environment is activated, install the required dependencies by running:
```bash
pip install -r requirements.txt
```