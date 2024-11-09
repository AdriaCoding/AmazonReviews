from datetime import datetime, date
from review import ReviewData, generate_review_id
from bs4 import BeautifulSoup
import email
from email.policy import default
import logging
import re



def convert_datetime_to_string(data):
    """
    Recursively convert datetime objects to strings in the given data.
    
    :param data: The data to convert.
    :return: The converted data.
    """
    if isinstance(data, dict):
        return {key: convert_datetime_to_string(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_datetime_to_string(item) for item in data]
    elif isinstance(data, (datetime, date)):
        return data.isoformat()
    else:
        return data
    

def parse_review_date_and_author(review_date_and_author: str):
    """
    Parse the author name and review date from the given string.
    
    :param review_date_and_author: The string containing the author and date.
    :return: A tuple containing the author name and review date.
    """
    if review_date_and_author == None:
        return None, None
    # Regular expression to match the pattern "Review by {author} on {date_string}"
    pattern = r"Review by (.+?) on (\d{1,2} \w+ \d{4})"
    match = re.match(pattern, review_date_and_author)
    
    if not match:
        logging.warning(f"data + author string : {review_date_and_author} does not match the expected format. Did you change the website language to ENGLISH??")
        return None, None
    
    author = match.group(1).strip()
    date_string = match.group(2).strip()
    
    # Mapping English month names to month numbers
    english_months = {
        'january': 1,
        'february': 2,
        'march': 3,
        'april': 4,
        'may': 5,
        'june': 6,
        'july': 7,
        'august': 8,
        'september': 9,
        'october': 10,
        'november': 11,
        'december': 12
    }

    # Parse the date string
    parts = date_string.split(' ')
    if len(parts) != 3:
        logging.warning(f"date string \'{date_string}\' does not have three parts separated by a whitespace: .")
    
    try:
        day = int(parts[0])
        month_name = parts[1].lower()
        month = english_months.get(month_name)
        if not month:
            raise ValueError(f"Invalid month name: {month_name}")
        year = int(parts[2])
        review_datetime = datetime(year, month, day)
        review_date = review_datetime.date()
    except ValueError as e:
        logging.error(f"Error parsing date: {e}")
        return None, None
    
    return review_date, author


def parse_mhtml(contents: bytes):
    """
    Parse .mhtml contents and extract data from the <div class="reviewContainer css-1d1jdxb eihx8d30"> elements.
    """
    # Parse the .mhtml content as a MIME message
    msg = email.message_from_bytes(contents, policy=email.policy.default)

    # Extract the HTML part from the multipart message
    html_content = None
    for part in msg.walk():
        if part.get_content_type() == 'text/html':
            html_content = part.get_payload(decode=True).decode(part.get_content_charset('utf-8'), errors='replace')
            break

    if not html_content:
        raise ValueError("No HTML content found in the .mhtml file.")
    return parse_html(html_content)

def parse_html(html_content: str):
    """
    Parse the HTML content and extract review data from the <div class="reviewContainer css-1d1jdxb eihx8d30"> elements.
    """
    # Parse the HTML content with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Retrieve the country from the header button
    country_button = soup.find('button', class_='partner-dropdown-button')
    country_code = None
    if country_button:
        country_text = country_button.get_text(strip=True)
        # Assuming the format is "<b>Brand</b> | Country"
        country_string = country_text.split('|')[-1].strip()
        # We also support spanish language, just in case.
        country_code_mapping = {
            'España': 'ES',
            'Italia': 'IT',
            'Francia': 'FR',
            'Alemania': 'DE',
            'Reino Unido': 'UK',
            'Países Bajos': 'NL',
            'Spain': 'ES',
            'Italy': 'IT',
            'France': 'FR',
            'Germany': 'DE',
            'United Kingdom': 'UK',
            'Netherlands': 'NL',
        }

        country_code = country_code_mapping.get(country_string)

    # Find all review containers
    reviews = soup.find_all('div', class_='reviewContainer css-1d1jdxb eihx8d30')
    
    # Extract relevant information from each review container
    extracted_reviews = []
    for review in reviews:
        
        # Extract ASIN from the id oh the h5 tag
        h5_tag = review.find('h5', id=True)
        asin = h5_tag['id'].split('-')[0]


        # Extract Brand from the list of four divs next to the picture, nanely,
        # Parent ASIn, Child ASIN, Product's star rating, and *Brand*
        brand = None
        divs = review.find_all('div', class_='css-yyccc7 e1d0wyfb3')
        if len(divs) >= 4:
            # Get the fourth div and its second child div
            brand_div = divs[3].find_all('div')[1]
            brand = brand_div.get_text(strip=True)


        # Extract Review date and author (from the div with class 'css-g7g1lz')
        review_date_and_author_div = review.find('span', class_='css-g7g1lz')
        review_date_and_author = review_date_and_author_div.get_text(strip=True) if review_date_and_author_div else None
        review_date, author = parse_review_date_and_author(review_date_and_author)

        # Extract Title (content inside <b> tag inside div with class 'css-bf47do eihx8d31')
        title_div = review.find('div', class_='css-bf47do eihx8d31')
        title = title_div.find('b').get_text(strip=True) if title_div and title_div.find('b') else None
        
        # Extract Body (content inside div with class 'css-tks6au eihx8d34')
        body_div = review.find('div', class_='css-tks6au eihx8d34')
        body = body_div.get_text(strip=True) if body_div else None
        
        # Extract Rating
        star_rating = review.find('kat-star-rating', class_='reviewRating')
        rating_value = None
        if star_rating and star_rating.has_attr('value'):
            try:
                rating_value = int(star_rating['value'])
            except ValueError:
                rating_value = None

        # Extract URL
        url_div = review.find('kat-link', class_='css-1sowyjy')
        url = url_div['href'] if url_div and url_div.has_attr('href') else None

        # Set scraped_on date
        scraped_on = date.today()

        # Set scraped_on date
        review_data = ReviewData(
            review_id=generate_review_id(author, title, review_date),
            country=country_code,
            asin=asin,
            brand=brand,
            review_date=review_date,
            author=author,
            verified=None,
            helpful=None,
            title=title,
            body=body,
            rating=rating_value,
            url=url,
            scraped_on=scraped_on
        )
        extracted_reviews.append(review_data)
    
    return extracted_reviews
