# Configuration Guide for Medical Scheduling Agent

## Environment Variables Setup

Create a `.env` file in your project root with the following variables:

```env
# Groq API Key (required for LLM)
GROQ_API_KEY=your_groq_api_key_here

# Email Service Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password_here
SMTP_FROM_EMAIL=your_email@gmail.com

# Twilio Account 1 - For Emails
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here

# Twilio Account 2 - For SMS
TWILIO_ACCOUNT_SID1=your_second_twilio_account_sid_here
TWILIO_AUTH_TOKEN1=your_second_twilio_auth_token_here
TWILIO_PHONE_NUMBER1=+1234567890

# Calendly API Key (optional - will use mock mode if not provided)
CALENDLY_API_KEY=your_calendly_api_key_here
```

## Service Configuration

### Email Service
- **Primary**: Uses SMTP configuration (Gmail, Outlook, etc.)
- **Fallback**: Uses Twilio Account 1 for email sending
- **Mock Mode**: If no credentials provided

### SMS Service
- **Primary**: Uses Twilio Account 2 for SMS sending
- **Mock Mode**: If no credentials provided

## How It Works

1. **Email Service**: 
   - First tries SMTP (Gmail/Outlook)
   - Falls back to Twilio Account 1 if SMTP fails
   - Uses mock mode if no credentials

2. **SMS Service**:
   - Uses Twilio Account 2 for all SMS
   - Uses mock mode if no credentials

3. **Service Detection**:
   - The agent automatically detects which services are available
   - Shows "Real SMTP" or "Mock Mode" for email
   - Shows "Real Twilio" or "Mock Mode" for SMS

## Testing

Run the agent to see which services are active:

```bash
python interactive_agent.py
```

The output will show:
```
📧 Email Service: Real SMTP / Mock Mode
📱 SMS Service: Real Twilio / Mock Mode
```

## Troubleshooting

1. **Email not sending**: Check SMTP credentials and app passwords
2. **SMS not sending**: Check Twilio Account 2 credentials
3. **Both in mock mode**: Verify your `.env` file has correct credentials
