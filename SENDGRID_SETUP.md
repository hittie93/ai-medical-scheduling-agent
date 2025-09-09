# SendGrid Email Configuration Guide

## SendGrid SMTP Settings

For SendGrid, use these SMTP settings in your `.env` file:

```env
# SendGrid SMTP Configuration
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=your_sendgrid_api_key_here
SMTP_FROM_EMAIL=your_verified_sender@yourdomain.com
```

## Important Notes:

1. **SMTP_USERNAME**: Always use `apikey` (not your SendGrid username)
2. **SMTP_PASSWORD**: Use your SendGrid API key (not your SendGrid password)
3. **SMTP_FROM_EMAIL**: Must be a verified sender in your SendGrid account
4. **SMTP_PORT**: Use `587` for TLS or `465` for SSL

## Getting Your SendGrid API Key:

1. Log in to your SendGrid account
2. Go to **Settings** → **API Keys**
3. Click **Create API Key**
4. Choose **Restricted Access** or **Full Access**
5. Copy the generated API key
6. Add it to your `.env` file as `SMTP_PASSWORD`

## Verifying Your Sender:

1. Go to **Settings** → **Sender Authentication**
2. Verify your domain or single sender email
3. Use the verified email as `SMTP_FROM_EMAIL`

## Testing Your Configuration:

Run the test script to verify your SendGrid setup:

```bash
python test_services.py
```

You should see:
- ✅ Email Service: Real SMTP
- ✅ Test Result: Success

## Troubleshooting:

- **"Connection unexpectedly closed"**: Check your API key and sender verification
- **"Authentication failed"**: Ensure SMTP_USERNAME is `apikey` and password is your API key
- **"Sender not verified"**: Verify your sender email in SendGrid dashboard
