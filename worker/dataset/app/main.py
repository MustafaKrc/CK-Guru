# worker/dataset/app/main.py
from shared.celery_config.app import create_celery_app

celery_app = create_celery_app(
    main_name="dataset_worker",
    include_tasks=["app.tasks"]
)