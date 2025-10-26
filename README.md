# CK-Guru

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**CK-Guru** is an open-source platform for Just-In-Time (JIT) software defect prediction. It helps development teams identify potentially defective code changes before they cause problems in production.

## What Does It Do?

CK-Guru analyzes Git repositories to predict which code changes are likely to introduce bugs. The platform:

- **Analyzes Repositories**: Extracts commit history, code metrics (CK & CommitGuru), and links GitHub issues to commits
- **Creates Datasets**: Generates clean, configurable datasets from repository data for ML training
- **Trains Models**: Builds defect prediction models using scikit-learn with automated hyperparameter optimization (Optuna)
- **Makes Predictions**: Identifies potentially defective code changes and explains why through visualizations
- **Provides Web Interface**: Modern UI for managing repositories, datasets, models, and viewing prediction insights

## Features

- **Repository Ingestion**: Automatically clones Git repositories and extracts CK metrics, CommitGuru metrics, and GitHub issue links
- **Dataset Management**: Create and clean custom datasets with configurable feature selection
- **Model Training**: Train scikit-learn models with Optuna-based hyperparameter optimization
- **Defect Prediction**: Predict defect-prone code changes with explainable AI insights (SHAP, feature importance, counterfactuals)
- **Web Interface**: Modern Next.js UI for managing the entire ML pipeline
- **Background Processing**: Celery workers handle long-running tasks (ingestion, dataset generation, training)
- **Scalable Storage**: MinIO object storage for datasets and model artifacts

## Architecture

CK-Guru uses a microservices architecture with Docker Compose:

- **Frontend**: Next.js/React UI served via Nginx
- **Backend**: FastAPI REST API
- **Workers**: Three Celery workers for ingestion, dataset processing, and ML tasks
- **Database**: PostgreSQL for metadata storage
- **Message Broker**: RabbitMQ for task distribution
- **Cache/Results**: Redis for Celery results
- **Object Storage**: MinIO (S3-compatible) for datasets and models
- **Monitoring**: Flower for task monitoring

## Installation

### Prerequisites

- **Docker** and **Docker Compose**: [Install Docker](https://docs.docker.com/engine/install/)
- **Git**: Required for repository cloning (for ingestion)

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/MustafaKrc/CK-Guru.git
   cd CK-Guru
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and change passwords, keys, and settings (especially default passwords)
   ```

3. **Start the application**:
   ```bash
   docker-compose up --build -d
   ```

4. **Access the application**:
   - Frontend UI: http://localhost:80
   - Backend API: http://localhost:8000/api/docs
   - Flower (Task Monitor): http://localhost:5555
   - MinIO Console: http://localhost:9001

The application automatically creates the MinIO bucket and runs database migrations on first start.

5. **Stop the application**:
   ```bash
   docker-compose down
   # To remove all data: docker-compose down -v
   ```

## Usage

1. **Register/Login**: Create an account at http://localhost:80
2. **Add Repository**: Enter a Git repository URL in the Repositories section
3. **Ingest Data**: Trigger ingestion to extract metrics and commit data (monitor progress in Flower)
4. **Create Dataset**: Configure and generate a dataset from ingested data
5. **Train Model**: Start a training or hyperparameter search job using your dataset
6. **Run Predictions**: Use trained models to predict defect-prone changes
7. **Analyze Results**: View XAI explanations (SHAP, feature importance) for predictions

## Technology Stack

- **Backend**: FastAPI, SQLAlchemy (async), Alembic, Pydantic
- **Frontend**: Next.js, React, TypeScript, shadcn/ui, Tailwind CSS
- **Workers**: Celery, RabbitMQ, Redis
- **Database**: PostgreSQL
- **Storage**: MinIO (S3-compatible)
- **ML**: Scikit-learn, Optuna, Pandas, NumPy
- **Metrics**: CK Tool, CommitGuru
- **Deployment**: Docker, Docker Compose

## Contributing

Contributions are welcome! 

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes and write tests
4. Ensure tests pass (`pytest`)
5. Commit with clear messages
6. Push to your fork and create a Pull Request

Please open an issue first to discuss significant changes.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [CK Tool](https://github.com/mauricioaniche/ck) for Java code metrics
- [CommitGuru](https://github.com/CommitAnalyzingService) for change-level analysis concepts
- Research on dataset creation: [JIT-SDP](https://github.com/MustafaKrc/JIT-SDP)
