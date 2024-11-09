from pydantic import BaseModel
from datetime import date
import json
import hashlib
from typing import Union

def generate_review_id(author, title, review_date):
    unique_string = f"{author}_{title}_{review_date}"
    return hashlib.sha256(unique_string.encode('utf-8')).hexdigest()

# The review data model defaults to "None" for most fields
class ReviewData(BaseModel):
    review_id:   str  = generate_review_id(None, None, None)
    country:     Union[str,None] = None
    asin:        Union[str,None] = None
    brand:       Union[str,None] = None
    review_date: Union[date,None] = None
    author:      Union[str,None] = None
    verified:    Union[bool,None] = None
    helpful:     Union[bool,None] = None
    title:       Union[str,None] = None
    body:        Union[str,None] = None
    rating:      Union[int,None] = None
    url:         Union[str,None] = None 
    scraped_on: date = date.today()

    model_config = {
        "json_encoders": {date: lambda v: v.isoformat()},
    }
    def model_dump(self, **kwargs):
        """
        Override pydantic's default model_dump method. Otherwise, we cannot JSON serialize the 'dates'.
        """
        data = super().model_dump(**kwargs)
        # Convert date fields to strings in YYYY-MM-DD format
        if self.review_date:
            data['review_date'] = self.review_date.isoformat()
        if self.scraped_on:
            data['scraped_on'] = self.scraped_on.isoformat()
        return data

def save_reviews_to_json(reviews: list[ReviewData], filename: str):
    """
    Save the list of ReviewData objects to a JSON file.
    """
    data = [review.model_dump() for review in reviews]
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_reviews_from_json(filename: str) -> list[ReviewData]:
    """
    Load the list of ReviewData objects from a JSON file.
    """
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    reviews = [ReviewData(**item) for item in data]
    return reviews
