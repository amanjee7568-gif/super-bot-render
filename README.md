# Super Bot - Complete Telegram Bot

A feature-rich Telegram bot with gaming, payments, and premium features.

## Features

- 🎮 Multiple games (Slots, Dice, Basketball, etc.)
- 💰 Dual wallet system (Game & Premium coins)
- 💎 Premium subscription with exclusive benefits
- 💳 UPI payment integration
- 🎁 Referral program
- 🔥 Daily login streak bonuses
- 📊 Admin panel with full control
- 🧑‍💼 Job vacancies section
- 📄 Marksheet generation

## Deployment

### Render Deployment

1. Fork this repository
2. Create a new app on Render dashboard
3. Connect your GitHub repository
4. Set environment variables from `.env.example`
5. Deploy the app

### Environment Variables

Required environment variables:

- `BOT_TOKEN` - Your Telegram bot token
- `ADMIN_ID` - Your Telegram user ID
- `CASHFREE_APP_ID` - Cashfree app ID
- `CASHFREE_SECRET_KEY` - Cashfree secret key
- `CASHFREE_WEBHOOK_SECRET` - Cashfree webhook secret
- `WEBHOOK_URL` - Your Render app URL

## Commands

### User Commands
- `/start` - Start the bot
- `/topremium <amount>` - Transfer coins to premium wallet

### Admin Commands
- `/setwinrate <first15> <after>` - Set game win rates
- `/approvepayment <payment_id>` - Approve payment
- `/rejectpayment <payment_id>` - Reject payment

## Support

For support, contact: @amanjee7568
