# CK-Guru

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) 

<!--
[![Build Status](https://img.shields.io/github/actions/workflow/status/your_username/CK-Guru/ci.yml?branch=main)](https://github.com/your_username/CK-Guru/actions) 
[![Coverage Status](https://coveralls.io/repos/github/your_username/CK-Guru/badge.svg?branch=main)](https://coveralls.io/github/your_username/CK-Guru?branch=main)  -->

CK-Guru is an open-source platform designed for Just-In-Time (JIT) software defect prediction. It analyzes Git repositories, extracts relevant metrics (including CK and CommitGuru metrics), allows for dataset creation and cleaning, facilitates ML model training and hyperparameter tuning (using Optuna), provides inference capabilities to predict potentially defective code changes and provides visualizations for explanation of inference results.

The platform features a web interface built with Next.js for managing repositories, datasets, models, jobs, and viewing prediction insights.

## Key Features

*   **Repository Management:** Add and manage Git repositories for analysis.
*   **Automated Ingestion:** Clones repositories and extracts comprehensive data:
    *   Commit history and metadata.
    *   CK metrics (Chidamber & Kemerer) using the [CK Tool](https://github.com/mauricioaniche/ck).
    *   [CommitGuru]([CommitGuru](https://github.com/CommitAnalyzingService)) metrics for change-level analysis.
    *   GitHub issue linking to commits.
*   **Dataset Generation:** Create custom datasets from ingested data with configurable features and cleaning rules.
*   **ML Model Training:** Train various defect prediction models (initially focused on Scikit-learn).
*   **Hyperparameter Optimization:** Utilize Optuna for automated hyperparameter search to find the best model configurations.
*   **Inference:** Run trained models to predict the defect-proneness of new code changes (integration with CI/CD planned).
*   **Web Interface:** Modern UI (built with Next.js and shadcn/ui) for:
    *   Managing repositories, datasets, models, and jobs.
    *   Viewing task status and results.
    *   Comparing model performance.
    *   Exploring prediction insights (XAI components).
    *   Managing user profiles and settings.
*   **Explainable AI (XAI):** Components for understanding model predictions (Feature Importance, SHAP values, Counterfactuals, Decision Paths).
*   **Task Queueing:** Uses Celery with RabbitMQ/Redis for handling background tasks (ingestion, dataset generation, ML).
*   **Containerized:** Fully containerized using Docker and Docker Compose for easy setup and deployment.
*   **Monitoring:** Includes Flower for monitoring Celery tasks.
*   **Object Storage:** Uses MinIO (S3-compatible) for storing datasets and model artifacts.

## Architecture Overview

CK-Guru employs a microservices-oriented architecture orchestrated via Docker Compose:

1.  **Frontend (`frontend/`):** A Next.js/React application providing the user interface. Served via Nginx.
2.  **Backend (`backend/`):** A FastAPI application serving the REST API, handling requests from the frontend, managing database interactions (via SQLAlchemy async), and dispatching tasks to workers. Uses Alembic for migrations.
3.  **Workers (`worker/`):** Separate Celery workers handling specific background tasks:
    *   **Ingestion Worker (`worker/ingestion/`):** Clones Git repositories, runs CK and CommitGuru tools, fetches GitHub issues, and persists initial data.
    *   **Dataset Worker (`worker/dataset/`):** Processes ingested data, applies cleaning rules, and generates final datasets in Parquet format.
    *   **ML Worker (`worker/ml/`):** Handles model training, hyperparameter search (Optuna), and inference tasks.
4.  **Shared Library (`shared/`):** Contains common code used by the backend and workers, including database models (SQLAlchemy), Pydantic schemas, configuration settings, Celery setup, and utility functions.
5.  **Database (PostgreSQL):** Stores metadata about repositories, commits, metrics, datasets, models, jobs, etc.
6.  **Message Broker (RabbitMQ):** Manages communication between the backend and Celery workers.
7.  **Result Backend (Redis):** Stores Celery task status and results (optional, but needed for status checking).
8.  **Object Storage (MinIO):** Stores large artifacts like generated datasets (.parquet) and trained models (.pkl).
9.  **Monitoring (Flower):** Web UI for monitoring Celery tasks.

## Getting Started

### Prerequisites

*   **Docker:** [Install Docker](https://docs.docker.com/engine/install/)
*   **Docker Compose:** Usually included with Docker Desktop. If not, [Install Docker Compose](https://docs.docker.com/compose/install/).
*   **Git:** Required by workers for cloning repositories.
*   **`.env` file:** Configuration is managed via environment variables, typically loaded from a `.env` file.

### Configuration

1.  **Copy `.env` file:** Create a `.env` file in the project root directory. You can start by copying `.env.example`
    
2.  **Adjust `.env` values:** Change passwords, keys, and other settings as required for your environment. **Especially change default passwords/keys.**

### Running with Docker Compose

This is the recommended way to run CK-Guru.

1.  **Build and Start Services:**
    ```bash
    docker-compose up --build -d
    ```
   

2.  **Bucket Creation (First Run):** Docker Compose includes an `mc` service that attempts to create the MinIO bucket defined in your `.env` file (`S3_BUCKET_NAME`) after MinIO starts. Check the logs (`docker-compose logs mc`) to ensure it succeeded or if the bucket already existed.

3.  **Database Migrations:** The `backend` service entrypoint automatically runs Alembic migrations (`alembic upgrade head`) on startup to ensure the database schema is up-to-date.

4.  **Access Services:**
    *   **Frontend UI:** [http://localhost:3000](http://localhost:3000)
    *   **Backend API Docs (Swagger):** [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
    *   **Backend API Docs (ReDoc):** [http://localhost:8000/api/redoc](http://localhost:8000/api/redoc)
    *   **MinIO Console:** [http://localhost:9001](http://localhost:9001) (Use `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` from `.env` to log in)
    *   **Flower (Celery Monitor):** [http://localhost:5555](http://localhost:5555)

5.  **Stopping Services:**
    ```bash
    docker-compose down
    ```
    To remove volumes (database data, MinIO data, etc.), use:
    ```bash
    docker-compose down -v
    ```

## Usage

1.  **Register:** Create an account via the frontend UI ([http://localhost:3000/register](http://localhost:3000/register)).
2.  **Login:** Sign in to your account ([http://localhost:3000/login](http://localhost:3000/login)).
3.  **Add Repository:** Navigate to the "Repositories" section and add a Git repository URL.
4.  **Ingest Data:** Trigger the ingestion process for the added repository. This will run background tasks (viewable in Flower or the Tasks page) to clone the repo, calculate metrics (CK, CommitGuru), and link GitHub issues.
5.  **Create Dataset:** Go to the "Datasets" section, select the repository, and create a new dataset. Configure features, the target variable (e.g., `is_buggy`), and apply desired cleaning rules. Trigger dataset generation.
6.  **Train Model / HP Search:** Once a dataset is `Ready`, navigate to "ML Jobs" or "Models" to start a training job or a hyperparameter search (Optuna) job, selecting the dataset and model type/configuration.
7.  **View Models & Compare:** Explore trained models in the "Models" section. Use the "Model Comparison" page to compare their performance metrics.
8.  **Run Inference:** Use a trained model to predict defect-proneness for specific inputs (e.g., simulated pull request data) via the "Inference" section or potentially through future CI integrations.
9.  **Prediction Insights:** Analyze the results of inference jobs, exploring XAI explanations for why the model made a particular prediction.

## Development

### Setup

1.  **Clone:** `git clone https://github.com/your_username/CK-Guru.git`
2.  **Backend & Shared:**
    *   Create a Python virtual environment: `python -m venv .venv`
    *   Activate it: `source .venv/bin/activate` (Linux/macOS) or `.venv\Scripts\activate` (Windows)
    *   Install development requirements: `pip install -r requirements-dev.txt`
3.  **Frontend:**
    *   Navigate to the frontend directory: `cd frontend`
    *   Install dependencies: `npm install` (or `yarn install` / `pnpm install`)
4.  **Environment:** Ensure you have a `.env` file configured as described in "Getting Started". You might need to adjust `DATABASE_URL`, `CELERY_BROKER_URL`, etc., if running services outside Docker Compose (e.g., pointing to `localhost`).

### Running Services Individually

While Docker Compose is recommended, you can run services individually:

*   **Dependencies:** Manually start PostgreSQL, RabbitMQ, Redis, and MinIO instances.
*   **Backend:**
    *   Run migrations: `alembic upgrade head` (ensure `DATABASE_URL` is set)
    *   Start API server: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload`
*   **Frontend:**
    *   `cd frontend`
    *   `npm run dev` (Access at http://localhost:3000)
*   **Workers:**
    *   Activate the virtual environment (`source .venv/bin/activate`).
    *   Start each worker type in separate terminals, ensuring `PYTHONPATH` includes the project root or using `python -m celery...`:
        ```bash
        # Ingestion Worker
        celery -A worker.ingestion.app.main.celery_app worker --loglevel=INFO -Q ingestion

        # Dataset Worker
        celery -A worker.dataset.app.main.celery_app worker --loglevel=INFO -Q dataset

        # ML Worker
        celery -A worker.ml.app.main.celery_app worker --loglevel=INFO -Q ml_queue
        ```

### Database Migrations

Alembic is used for database schema migrations.

*   **Apply Migrations:** `alembic upgrade head`
*   **Create New Migration:** `alembic revision --autogenerate -m "Your description"` (After changing SQLAlchemy models in `shared/db/models/`)
*   **Check Current Revision:** `alembic current`

### Running Tests

Tests are located in the `tests/` directory and use `pytest`.

1.  Ensure development requirements are installed (`pip install -r requirements-dev.txt`).
2.  Make sure necessary services (like a test database if needed by tests) are running or mocked appropriately.
3.  Run tests from the project root:
    ```bash
    pytest
    ```
    To run with coverage:
    ```bash
    pytest --cov=. --cov-report=term-missing
    ```

## Technology Stack

*   **Backend:** Python, FastAPI, SQLAlchemy (async with asyncpg), Alembic, Pydantic
*   **Frontend:** TypeScript, React, Next.js, shadcn/ui, Tailwind CSS, Nginx
*   **Task Queue:** Celery, RabbitMQ (Broker), Redis (Result Backend)
*   **Database:** PostgreSQL
*   **Object Storage:** MinIO (S3 Compatible)
*   **ML/Data:** Pandas, NumPy, Scikit-learn, Optuna, PyArrow
*   **Containerization:** Docker, Docker Compose
*   **Code Metrics:** CK Tool (Java), CommitGuru (Python implementation)
*   **Testing:** Pytest
*   **Monitoring:** Flower

## Contributing

Contributions are welcome! Please follow these general steps:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix (`git checkout -b feature/your-feature-name` or `bugfix/issue-number`).
3.  Make your changes.
4.  Write tests for your changes.
5.  Ensure all tests pass (`pytest`).
6.  Format your code (e.g., using `black`, `isort`, `ruff`).
7.  Commit your changes with clear messages.
8.  Push your branch to your fork (`git push origin your-branch-name`).
9.  Create a Pull Request against the `main` branch of the original repository.

Please open an issue first to discuss significant changes or new features.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. <!-- Make sure the LICENSE file exists and reflects your choice -->

##  Acknowledgements

*   This project utilizes the [CK (Chidamber & Kemerer) tool](https://github.com/mauricioaniche/ck) for Java code metrics.
*   The defect prediction concepts are inspired by research in the field, including work related to [CommitGuru](https://github.com/CommitAnalyzingService) metrics.
*   The research behind dataset creation and cleaning can be found [here](https://github.com/MustafaKrc/JIT-SDP).
