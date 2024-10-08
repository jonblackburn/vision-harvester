# harvester.py
# Harvests images from Flickr and Pinterest to train the spooky api model
import os
import requests
import uuid
import json
from datetime import datetime
from bs4 import BeautifulSoup
from bs4.diagnose import diagnose 
from urllib.parse import quote_plus
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

base_dir = "spooky-image-harvester/harvested"
def harvest_images(search_term, source, label):
    # Create the harvested directory if it doesn't exist
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    
    # Create a folder for the search term
    folder_name = label.replace(" ", "_")
    folder_path = os.path.join(base_dir, folder_name)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    if source.lower() == "pinterest":
        harvest_from_pinterest(search_term, folder_path)
    elif source.lower() == "flickr":
        harvest_from_flickr(search_term, folder_path)
    else:
        print(f"Unsupported source: {source}. Defaulting to Flickr.")
        harvest_from_flickr(search_term, folder_path)


def create_image_index(image_data):
    index_file = os.path.join(base_dir, "image_index.json")
    
    # Load existing data if the file exists
    if os.path.exists(index_file):
        with open(index_file, 'r') as f:
            existing_data = json.load(f)
    else:
        existing_data = []
    
    # Add new image data
    existing_data.extend(image_data)
    
    # Write updated data back to the file
    with open(index_file, 'w') as f:
        json.dump(existing_data, f, indent=2)

def add_to_image_index(image_name, image_url, source, label):
    image_data = {
        "image_name": image_name,
        "image_url": image_url,
        "source": source,
        "label": label,
        "date_added": datetime.now().isoformat()
    }
    create_image_index([image_data])

def image_exists_in_index(image_url, source):
    index_file = os.path.join(base_dir, "image_index.json")
    
    if not os.path.exists(index_file):
        return False
    
    with open(index_file, 'r') as f:
        image_index = json.load(f)
    
    return any(image['image_url'] == image_url and image['source'] == source for image in image_index)


def harvest_from_flickr(search_term, folder_path):
    url = f"https://www.flickr.com/search/?text={quote_plus(search_term)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    print(f"Getting images from {url}")

    # use headless selenium to get the page and get the complete html response
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=old')
    driver = webdriver.Chrome(options=options)
    driver.get(url)

    #implicit wait for 2 seconds to allow the page to load more content.
    #driver.implicitly_wait(2)
    html = driver.page_source
    driver.quit()

    # parse the html with beautiful soup
    soup = BeautifulSoup(html, "html.parser")
    container_elements = soup.find_all("a", class_="overlay")    
    print(f"Found {len(container_elements)} images")
    
    # The container elements are the thumbnail overlay anchors. So we should be able to use the href to make the full size image request
    for i, container in enumerate(container_elements):
        try:
            embedded_image_url = container['href']
            full_image_url = f"https://www.flickr.com{embedded_image_url}sizes/l/"
            if not image_exists_in_index(full_image_url, "flickr"):
                print(f"Downloading image {full_image_url}")
                response = requests.get(full_image_url)
                if response.status_code == 200:

                    # Parse the full image page to get the actual image source
                    full_image_soup = BeautifulSoup(response.content, "html.parser")
                    img_container = full_image_soup.find("div", id="allsizes-photo")
                    content_type = ''
                    if img_container:
                        img_tag = img_container.find("img")
                        if img_tag and 'src' in img_tag.attrs:
                            actual_image_url = img_tag['src']
                            print(f"Downloading full-size image from {actual_image_url}")
                            img_response = requests.get(actual_image_url)
                            if img_response.status_code == 200:
                                response = img_response  # Update response to use the full-size image content
                                content_type = response.headers['Content-Type'].split('/')[-1]
                            else:
                                print(f"Failed to download full-size image. Status code: {img_response.status_code}")
                        else:
                            print("Could not find image source in the full-size page")
                    else:
                        print("Could not find the full-size image container")

                    image_name_guid = str(uuid.uuid4())
                    with open(os.path.join(folder_path, f"{image_name_guid}.{content_type}"), "wb") as f:
                        f.write(response.content)

                    add_to_image_index(image_name_guid, full_image_url, "flickr", label)                    
                else:
                    print(f"Failed to download image from Flickr. Status code: {response.status_code}")
            else:
                print(f"Image {full_image_url} has already been harvested")

        except Exception as e:
            print(f"Error downloading image from Flickr: {e}")


def harvest_from_pinterest(search_term, folder_path):
    print("Pinterest harvest not implemented yet")

# Example usage
if __name__ == "__main__":
    search_term = input("Enter search term: ")
    label = input("Enter label: ")
    source = input("Enter source (flickr/pinterest): ")
    harvest_images(search_term, source, label)
