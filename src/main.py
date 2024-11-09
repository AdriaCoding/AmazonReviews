from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from seleniumbase import get_driver
import time
from transform import parse_html
from review import ReviewData, save_reviews_to_json, load_reviews_from_json
from load import upload_to_staging_table, execute_merge

parsed_data_store: list[ReviewData] = []

markeplace_names = {
    "ES": "Spain",
    "UK": "United Kingdom",
    "FR": "France",
    "DE": "Germany",
    "NL": "Netherlands",
    "IT": "Italy",
    "SE": "Sweden",
    "PL": "Poland",
}

def init_driver():
    # Define Chrome arguments as a list
    chromium_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-infobars",
        # "--headless",  # Uncomment if you want to run in headless mode
    ]
    
    # Initialize the driver using SeleniumBase's get_driver function with chromium_arg
    driver = get_driver(browser="chrome", headless=False, chromium_arg=chromium_args)
    return driver

def is_logged_in(driver):
    try:
        driver.find_element(By.CLASS_NAME, 'partner-dropdown-button')  # Update selector as needed
        return True
    except NoSuchElementException:
        return False
    

def select_marketplace(driver, account="Zenement", marketplace_name="España"):
    wait = WebDriverWait(driver, 10) 

    try:
        # Click the marketplace dropdown
        marketplace_dropdown = wait.until(EC.element_to_be_clickable(
            (By.CLASS_NAME, 'dropdown-account-switcher-header-label')))
        marketplace_dropdown.click()
        
        # Wait for the options container to be visible
        wait.until(EC.visibility_of_element_located(
            (By.CLASS_NAME, 'dropdown-account-switcher-list-scrollable')))
        
        # Click the account container with title=account
        account_xpath = f'//div[@class="dropdown-account-switcher-list-item" and @title="{account}"]'
        account_element = wait.until(EC.element_to_be_clickable(
            (By.XPATH, account_xpath)))
        account_element.click()
        
        # Wait for the marketplace options to be visible
        wait.until(EC.visibility_of_element_located(
            (By.XPATH, '//div[contains(@class, "dropdown-account-switcher-list-item-indented")]')))
        
        # Locate and click the marketplace with title=marketplace_name
        option_xpath = f'//div[contains(@class, "dropdown-account-switcher-list-item-indented") and @title="{marketplace_name}"]'
        marketplace_option = wait.until(EC.element_to_be_clickable(
            (By.XPATH, option_xpath)))
        marketplace_option.click()
        
        # Optionally, wait for the page to update after selection
        #wait.until(EC.presence_of_element_located((By.ID, 'some-unique-page-element')))  # Adjust as needed

    except TimeoutException:
        print("Timed out waiting for select_marketplace elements to become available.")
    except NoSuchElementException as e:
        print(f"Element not found when select_marketplace: {e}")
    except Exception as e:
        print(f"An unexpected error occurred at select_marketplace: {e}")

def select_english_language(driver):
    wait = WebDriverWait(driver, 10) 

    try:
        # Click the marketplace dropdown
        language_dropdown_container = wait.until(EC.element_to_be_clickable(
            (By.CLASS_NAME, 'locale-icon-wrapper')))
        language_dropdown_container.click()
        
        # Wait for the flyout (dropdown) to appear
        localeList = wait.until(EC.visibility_of_element_located(
            (By.CLASS_NAME, 'locale-list-body')))

        
        # Locate and click the English language option
        english_option_xpath = './/a[@class="locale-list-item" and .//div[@class="locale-list-item-language" and normalize-space(text())="English"]]'
        english_option = localeList.find_element(By.XPATH, english_option_xpath)
        english_option.click()

        # Optionally, wait for the page to update after selection
        #wait.until(EC.presence_of_element_located((By.ID, 'some-unique-page-element')))  # Adjust as needed

    except TimeoutException:
        print("Timed out waiting for Language selection elements to become available.")
    except NoSuchElementException as e:
        print(f"Element for language switching not found: {e}")
    except Exception as e:
        print(f"An unexpected error occurred when switching language: {e}")

def get_num_pages(driver):
    try:
        wait = WebDriverWait(driver, 10)
        pagination = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'css-9ymdzb')))
        total_pages = int(pagination.get_attribute('aria-valuemax'))
        current_page = int(pagination.get_attribute('aria-valuenow'))    
        return total_pages, current_page
    except Exception as e:
        print(f"Error getting number of pages: {e}")
        return 1, 1  # Assume at least one page if unable to determine

def build_url(driver, page=1, page_size=50):
    base_url = driver.current_url.split('/')[0] + '//' + driver.current_url.split('/')[2]
    return f"{base_url}/brand-customer-reviews/ref=xx_crvws_foot_xx?pageSize={page_size}&pageNumber={page}"

def paginate(driver):
    all_reviews = []
    total_pages, current_page = get_num_pages(driver)
    for page_num in range(current_page, total_pages + 1):
        print(f"Scraping page {page_num} of {total_pages}")
        
        # Wait for the reviews to be present
        wait = WebDriverWait(driver, 10)
        retries = 3
        while retries > 0:
            try:
                # Wait until at least one review is present
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'reviewContainer')))
                break  # Success, break out of retry loop
            except TimeoutException as e:
                retries -= 1
                print(f"Error waiting for reviews to load on page {page_num}: {e}")
                if retries > 0:
                    print(f"Retrying... ({retries} retries left)")
                    time.sleep(2)  # Wait before retrying
                else:
                    print("Failed to load reviews after retries.")
                    return all_reviews  # Return what we've collected so far
        
        html_content = driver.page_source
        reviews = parse_html(html_content)
        if not reviews:
            print(f"No reviews found on page {page_num}.")
            # Decide what to do: continue, retry, or break
            # For now, we'll continue to the next page
        else:
            all_reviews.extend(reviews)
        
        if page_num < total_pages:
            try:
                driver.get(build_url(driver, page_num + 1))
                time.sleep(2)  # Adjust sleep time as needed
            except Exception as e:
                print(f"Could not navigate to page {page_num + 1}: {e}")
                break
    return all_reviews


def main():
    driver = init_driver()
    driver.get("https://sellercentral.amazon.com/")
    input("\n\nPlease log in, and select any Marketplace. Then press Enter to continue...")

    select_english_language(driver)
    driver.get(build_url(driver))
    extraction_confirmed = False
    reviews_to_display={}
    while not extraction_confirmed:
        for marketplace in markeplace_names.keys():
            time.sleep(2)
            select_marketplace(driver, "Zenement", markeplace_names[marketplace])
            time.sleep(2)
            driver.get(build_url(driver))
            wait = WebDriverWait(driver, 10)
            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'reviewContainer')))
                reviews = paginate(driver)
                print(f"Scraped {len(reviews)} reviews from {marketplace}.")
                parsed_data_store.extend(reviews)
                if reviews:
                    reviews_to_display[marketplace] = reviews[0]
            except Exception as e:
                print(f"Error scraping reviews for marketplace {marketplace}: {e}")
                reviews = []
        
        print(f"Total reviews scraped: {len(reviews)}")
        for marketplace, review in reviews_to_display.items():
            print(f"Sample review from {marketplace}:\n {review.model_dump()}\n")
        user_input = input("Do you want to accept these reviews and continue? (y/n): ")
        if user_input.lower() == 'y':
            extraction_confirmed = True
        else:
            print(f"Retrying extraction for all marketplaces...")
            reviews.clear()
    driver.quit()


    # Attempt to upload data to GBQ
    try:
        print("Data extraction complete. Loading data to GBQ...")
        upload_to_staging_table(parsed_data_store)
        execute_merge()
        print("Data uploaded successfully.")
    except Exception as e:
        print(f"Error uploading data to GBQ: {e}")
        # Save the parsed data store to JSON file
        print("Saving parsed data to JSON file...")
        save_reviews_to_json(parsed_data_store, 'parsed_data_store.json')
        print("Data has been saved to 'parsed_data_store.json'. You can reload it later for uploading.")

def retry_upload():
    try:
        print("Loading parsed data from 'parsed_data_store.json'...")
        parsed_data_store = load_reviews_from_json('parsed_data_store.json')
        print(f"Loaded {len(parsed_data_store)} reviews.")
        
        print("Attempting to upload data to GBQ...")
        upload_to_staging_table(parsed_data_store)
        execute_merge()
        print("Data uploaded successfully.")
    except Exception as e:
        print(f"Error uploading data to GBQ: {e}")
        print("Please check the error and try again.")

if __name__ == "__main__":
    main()
