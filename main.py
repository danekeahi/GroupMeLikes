from groupy import Client
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import csv
import time
from datetime import datetime
import requests
import logging

# Configure logging to track script progress and errors
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Validate environment variables to ensure all required variables are set
spreadsheet_id = os.environ.get("SPREADSHEET_ID")
groupme_token = os.environ.get("TOKEN")
groupme_id = os.environ.get("GROUPME_ID")
if not spreadsheet_id or not groupme_token or not groupme_id:
    raise ValueError("Missing required environment variables: SPREADSHEET_ID, TOKEN, or GROUPME_ID")

# Google Sheets API Setup
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
client = gspread.authorize(credentials)
spreadsheet = client.open_by_key(spreadsheet_id)

# GroupMe API Setup
groupme_client = Client.from_token(groupme_token)
nu = groupme_client.groups.get(groupme_id)

# Create a mapping of user IDs to both full names and nicknames
id_to_member = {member.user_id: {"name": member.name, "nickname": member.nickname} for member in nu.members}

def fetch_messages_with_retry(group, max_retries=5):
    """
    Fetch messages from the GroupMe API with retry logic to handle rate limits (429 errors).
    :param group: The GroupMe group object
    :param max_retries: Maximum number of retries for rate-limited requests
    :return: Iterable of messages
    """
    retries = 0
    while retries < max_retries:
        try:
            return group.messages.list_all()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Too Many Requests
                wait_time = 2 ** retries  # Exponential backoff
                logging.warning(f"Rate limit hit. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                retries += 1
            else:
                logging.error(f"HTTP Error: {e}")
                raise
    raise Exception("Max retries exceeded")

def main():
    # Dictionaries to track total likes and message counts per user
    like_counter = {}
    message_counter = {}
    # List to store messages for sorting and analysis
    messages_list = []

    # Open a CSV file to write messages
    with open("out.csv", "w") as f:
        writer = csv.writer(f)
        # Write the header row
        writer.writerow(["Created At", "Sender ID", "Message Text", "Like Count", "Attachment Count"])

        # Fetch and process messages from the GroupMe group
        for message in fetch_messages_with_retry(nu):
            sender_id = message.data["sender_id"]
            like_count = len(message.favorited_by)
            message_text = message.text or "[No Text]"  # Handle case where text is None

            # Update like and message counters for the sender
            like_counter[sender_id] = like_counter.get(sender_id, 0) + like_count
            message_counter[sender_id] = message_counter.get(sender_id, 0) + 1

            # Append the message details to the list
            messages_list.append({
                "created_at": message.created_at,
                "sender_id": sender_id,
                "text": message_text,
                "like_count": like_count
            })

            # Write the message data to the CSV file
            writer.writerow([message.created_at, sender_id, message_text, like_count, len(message.attachments)])

            # Throttle requests to avoid hitting the rate limit
            time.sleep(0.5)

    # Sort messages by like count in descending order
    messages_list.sort(key=lambda x: x["like_count"], reverse=True)

    # Sort the like counter dictionary by total likes in descending order
    sorted_likes = sorted(like_counter.items(), key=lambda x: x[1], reverse=True)

    # Prepare data for Google Sheets
    sheet_data = [["Name", "Nickname", "Total Likes", "Average Likes"]]
    for user_id, total_likes in sorted_likes:
        # Get user details or default to "Unknown"
        member_data = id_to_member.get(user_id, {"name": "Unknown", "nickname": "Unknown"})
        name = member_data["name"]
        nickname = member_data["nickname"]
        message_count = message_counter.get(user_id, 1)  # Avoid division by zero
        average_likes = total_likes / message_count  # Calculate average likes per message
        sheet_data.append([name, nickname, total_likes, round(average_likes, 2)])

    # Add the most liked messages to the sheet
    sheet_data.append([])  # Blank row for separation
    sheet_data.append(["Most Liked Messages"])
    sheet_data.append(["Created At", "Name", "Nickname", "Like Count", "Message Text"])

    for message in messages_list[:15]:  # Top 15 most liked messages
        member_data = id_to_member.get(message["sender_id"], {"name": "Unknown", "nickname": "Unknown"})
        name = member_data["name"]
        nickname = member_data["nickname"]
        created_at = message["created_at"]
        if isinstance(created_at, datetime):
            created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")  # Convert datetime to string

        sheet_data.append([
            created_at,
            name,
            nickname,
            message["like_count"],
            message["text"]
        ])

    # Write data to Google Sheets
    worksheet = spreadsheet.sheet1  # Target the first sheet
    worksheet.clear()  # Clear existing data
    worksheet.update(sheet_data)  # Update with new data

if __name__ == "__main__":
    main()
