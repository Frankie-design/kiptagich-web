import africastalking

# 1. Initialize Africa's Talking with Production Credentials
# Replace 'your_live_username' and 'your_live_api_key' with your actual AT credentials
USERNAME = "your_live_username"  
API_KEY = "your_live_api_key"    

africastalking.initialize(USERNAME, API_KEY)
sms = africastalking.SMS

def send_irrigation_alert(owner_name, phone_number, plot_id):
    """
    Sends a live, real-time background SMS text message to the farmer 
    whenever their soil moisture status hits a Critical threshold.
    """
    message = (
        f"Alert for {owner_name} (Plot ID: {plot_id}): Your plot has reached a "
        f"CRITICAL moisture threshold based on GNSS-R analysis. Please initiate irrigation."
    )
    
    # Ensure the phone number is in international format (e.g., +2547XXXXXXXX)
    recipients = [phone_number]
    
    try:
        # This executes the real cellular network dispatch quietly in the background
        response = sms.send(message, recipients)
        print(f"--- BACKGROUND LOG: Live SMS successfully dispatched to {owner_name} ({phone_number}) ---")
        print(f"Response Details: {response}")
        return True
    except Exception as e:
        print(f"--- BACKGROUND LOG: Failed to send live SMS to {owner_name}. Error: {e} ---")
        return False
