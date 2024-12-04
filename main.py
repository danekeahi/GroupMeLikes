from groupy import Client
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import csv
import time
from datetime import datetime

# Google Sheets API Setup
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
client = gspread.authorize(credentials)
spreadsheet_id = os.environ.get("SPREADSHEET_ID")
spreadsheet = client.open_by_key(spreadsheet_id)  # Change to your spreadsheet name

# GroupMe API Setup
groupme_client = Client.from_token(os.environ.get("TOKEN"))
nu = groupme_client.groups.get(os.environ.get("GROUPME_ID"))  # Replace with your GroupMe group ID

# Create a mapping of user IDs to both full names and nicknames
id_to_member = {member.user_id: {"name": member.name, "nickname": member.nickname} for member in nu.members}

def main():
    # Dictionary to keep track of total likes per user
    like_counter = {}
    # Dictionary to keep track of message count per user
    message_counter = {}
    # List to store messages for finding the most liked ones
    messages_list = []

    with open("out.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(["Created At", "Sender ID", "Message Text", "Like Count", "Attachment Count"])  # Header

        # Iterate over messages in the GroupMe group
        for message in nu.messages.list_all():
            sender_id = message.data["sender_id"]
            like_count = len(message.favorited_by)
            message_text = message.text or "[No Text]"  # Handle case where text may be None

            # Update like count and message count for the sender
            like_counter[sender_id] = like_counter.get(sender_id, 0) + like_count
            message_counter[sender_id] = message_counter.get(sender_id, 0) + 1

            # Store the message data for sorting later
            messages_list.append({
                "created_at": message.created_at,
                "sender_id": sender_id,
                "text": message_text,
                "like_count": like_count
            })

            # Write message data to CSV
            writer.writerow([message.created_at, sender_id, message_text, like_count, len(message.attachments)])

    # Sort messages by like count in descending order to get the most liked messages
    messages_list.sort(key=lambda x: x["like_count"], reverse=True)

    # Sort the like_counter dictionary by total likes in descending order
    sorted_likes = sorted(like_counter.items(), key=lambda x: x[1], reverse=True)

    # Prepare data for Google Sheets
    sheet_data = [["Name", "Nickname", "Total Likes", "Average Likes"]]
    for user_id, total_likes in sorted_likes:  # Use sorted list
        member_data = id_to_member.get(user_id, {"name": "Unknown", "nickname": "Unknown"})
        name = member_data["name"]
        nickname = member_data["nickname"]
        message_count = message_counter.get(user_id, 1)  # Avoid division by zero
        average_likes = total_likes / message_count  # Calculate average likes per message
        sheet_data.append([name, nickname, total_likes, round(average_likes, 2)])  # Round to 2 decimal places

    # Add the most liked messages to the sheet data next to total likes
    sheet_data.append([])  # Add a blank row for separation
    sheet_data.append(["Most Liked Messages"])
    sheet_data.append(["Created At", "Name", "Nickname", "Like Count", "Message Text"])

    for message in messages_list[:15]:  # Get top 10 most liked messages, adjust as needed
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

    # Output data to Google Sheets
    worksheet = spreadsheet.sheet1  # Modify to target a specific sheet if needed
    worksheet.clear()  # Clear existing data
    worksheet.update(sheet_data)  # Update with new data

if __name__ == "__main__":
    main()
