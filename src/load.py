from google.cloud import bigquery
from google.oauth2 import service_account
import os
import logging
from review import load_reviews_from_json

def get_gbq_credentials():
    env_var = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    sa_file = env_var if env_var else  "./gbq-serviceaccount-credentials.json"
    if not os.path.exists(sa_file):
        logging.warning(f"Service acount credentials for gbq not found at path {sa_file}")
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            raise EnvironmentError("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
    return service_account.Credentials.from_service_account_file(sa_file)

def upload_to_staging_table(reviews_data):
    client = bigquery.Client(credentials=get_gbq_credentials())
    table_id = 'testing-dashboard20211125.reviews.staging_reviews'
    rows_to_insert = [review.model_dump() for review in reviews_data]

    job = client.load_table_from_json(
        rows_to_insert,
        table_id,
        job_config=bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
        )
    )
    try:
        job.result()
        logging.info(f"Loaded {len(rows_to_insert)} rows into {table_id}.")
    except Exception as e:
        logging.error(f"Error loading data to BigQuery: {e}")

def execute_merge():
    client = bigquery.Client(credentials=get_gbq_credentials())

    merge_query = """
    MERGE `testing-dashboard20211125.reviews.reviews` AS T
    USING (
    WITH Deduped_S AS ( -- Deduplication subquery for staging table
        SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY review_id
            ORDER BY scraped_on DESC  -- or another column to determine the most relevant row
        ) AS rn
        FROM `testing-dashboard20211125.reviews.staging_reviews`
    )
    SELECT
        review_id, country, asin, brand, review_date, author, verified,
        helpful, title, body, rating, url, scraped_on
    FROM Deduped_S
    WHERE rn = 1
    ) AS S    
    ON T.review_id = S.review_id
    WHEN MATCHED THEN
      UPDATE SET
        T.country = S.country,
        T.asin = S.asin,
        T.brand = S.brand,
        T.review_date = S.review_date,
        T.author = S.author,
        T.title = S.title,
        T.body = S.body,
        T.rating = S.rating,
        T.url = S.url,
        T.scraped_on = S.scraped_on
    WHEN NOT MATCHED THEN
      INSERT (
        review_id, country, asin, brand, review_date, author, verified,
        helpful, title, body, rating, url, scraped_on
      )
      VALUES (
        S.review_id, S.country, S.asin, S.brand, S.review_date, S.author, CAST(S.verified AS BOOL),
        CAST(S.helpful AS BOOL), S.title, S.body, S.rating, S.url, S.scraped_on
      );
    """

    try:
        query_job = client.query(merge_query)
        query_job.result()
        logging.info("Merge operation completed successfully.")
    except Exception as e:
        logging.error(f"Error executing merge query: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parsed_data_store = load_reviews_from_json('parsed_data_store.json')
    upload_to_staging_table(parsed_data_store)
    execute_merge()
