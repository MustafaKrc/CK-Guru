import re
from typing import Any

from sqlalchemy.orm import as_declarative, declared_attr

@as_declarative()
class Base:
    id: Any
    __name__: str

    # Generate __tablename__ automatically
    # Converts CamelCase class names to snake_case table names
    @declared_attr
    def __tablename__(cls) -> str:
        # Use regex to convert CamelCase to snake_case
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower()
        # Optional: add an 's' for pluralization if desired
        # if not name.endswith('s'):
        #     name += 's'
        return name
    