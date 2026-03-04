import json
from pathlib import Path
from config.settings import DEMO_MODE, DATA_DIR
from db.database import get_company_count, insert_company, insert_thesis, init_db
from models.company import Company


def is_demo_mode() -> bool:
    return DEMO_MODE


def load_sample_data():
    """Load sample companies and default thesis into the database if empty."""
    init_db()
    if get_company_count() > 0:
        return

    # Load sample companies
    sample_path = DATA_DIR / "sample_companies.json"
    if sample_path.exists():
        companies = json.loads(sample_path.read_text())
        for c_data in companies:
            company = Company(**{k: v for k, v in c_data.items() if k in Company.__dataclass_fields__})
            insert_company(company)

    # Load default thesis
    thesis_path = Path(__file__).resolve().parent.parent / "config" / "default_thesis.json"
    if thesis_path.exists():
        thesis = json.loads(thesis_path.read_text())
        insert_thesis(thesis)

    # Load sample news
    news_path = DATA_DIR / "sample_news.json"
    if news_path.exists():
        from db.database import insert_news
        news_items = json.loads(news_path.read_text())
        for item in news_items:
            insert_news(item)
