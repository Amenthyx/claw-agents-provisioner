export interface ChannelField {
  key: string;
  label: string;
  placeholder: string;
  type: 'text' | 'password' | 'number' | 'toggle';
}

export interface ChannelDef {
  id: string;
  name: string;
  icon: string;
  description: string;
  fields: ChannelField[];
  guideSteps: string[];
}

export const CHANNELS: ChannelDef[] = [
  {
    id: 'telegram',
    name: 'Telegram',
    icon: 'Send',
    description: 'Connect via Telegram Bot API',
    fields: [
      { key: 'botToken', label: 'Bot Token', placeholder: '123456:ABC-DEF...', type: 'password' },
      { key: 'chatId', label: 'Chat ID', placeholder: '-1001234567890', type: 'text' },
    ],
    guideSteps: [
      'Open @BotFather on Telegram and create a new bot with /newbot',
      'Copy the bot token provided by BotFather',
      'Add the bot to your group/channel and get the chat ID',
      'Paste both values above and test the connection',
    ],
  },
  {
    id: 'whatsapp',
    name: 'WhatsApp',
    icon: 'MessageCircle',
    description: 'Connect via WhatsApp Business API',
    fields: [
      { key: 'phoneNumberId', label: 'Phone Number ID', placeholder: '1234567890', type: 'text' },
      { key: 'accessToken', label: 'Access Token', placeholder: 'EAAx...', type: 'password' },
    ],
    guideSteps: [
      'Go to Meta for Developers and create a WhatsApp Business app',
      'Navigate to WhatsApp > API Setup to get your Phone Number ID',
      'Generate a permanent access token from the app settings',
      'Paste both values above and test the connection',
    ],
  },
  {
    id: 'slack',
    name: 'Slack',
    icon: 'Hash',
    description: 'Connect via Slack Bot or Webhook',
    fields: [
      { key: 'webhookUrl', label: 'Webhook URL', placeholder: 'https://hooks.slack.com/services/...', type: 'text' },
      { key: 'botToken', label: 'Bot Token', placeholder: 'xoxb-...', type: 'password' },
      { key: 'channel', label: 'Channel', placeholder: '#general', type: 'text' },
    ],
    guideSteps: [
      'Create a Slack app at api.slack.com/apps',
      'Enable Incoming Webhooks and create a webhook URL',
      'Install the app to your workspace and copy the Bot Token',
      'Specify the target channel and test the connection',
    ],
  },
  {
    id: 'discord',
    name: 'Discord',
    icon: 'Gamepad2',
    description: 'Connect via Discord Bot',
    fields: [
      { key: 'botToken', label: 'Bot Token', placeholder: 'MTk...', type: 'password' },
      { key: 'channelId', label: 'Channel ID', placeholder: '1234567890', type: 'text' },
    ],
    guideSteps: [
      'Go to discord.com/developers/applications and create a new application',
      'Navigate to Bot section and copy the bot token',
      'Enable Developer Mode in Discord settings, right-click a channel to copy its ID',
      'Invite the bot to your server using the OAuth2 URL Generator',
    ],
  },
  {
    id: 'email',
    name: 'Email / SMTP',
    icon: 'Mail',
    description: 'Send notifications via email',
    fields: [
      { key: 'host', label: 'SMTP Host', placeholder: 'smtp.gmail.com', type: 'text' },
      { key: 'port', label: 'Port', placeholder: '587', type: 'number' },
      { key: 'username', label: 'Username', placeholder: 'user@example.com', type: 'text' },
      { key: 'password', label: 'Password', placeholder: 'app-password', type: 'password' },
      { key: 'fromAddress', label: 'From Address', placeholder: 'noreply@example.com', type: 'text' },
      { key: 'tls', label: 'Enable TLS', placeholder: '', type: 'toggle' },
    ],
    guideSteps: [
      'Get your SMTP server details from your email provider',
      'For Gmail, use smtp.gmail.com with port 587 and an App Password',
      'For Office 365, use smtp.office365.com with port 587',
      'Enter your credentials above and test the connection',
    ],
  },
  {
    id: 'webhook',
    name: 'Custom Webhook',
    icon: 'Webhook',
    description: 'Send to any HTTP endpoint',
    fields: [
      { key: 'url', label: 'Webhook URL', placeholder: 'https://api.example.com/hook', type: 'text' },
      { key: 'method', label: 'HTTP Method', placeholder: 'POST', type: 'text' },
      { key: 'authHeader', label: 'Authorization Header', placeholder: 'Bearer xxx', type: 'password' },
    ],
    guideSteps: [
      'Provide the full URL of your webhook endpoint',
      'Choose HTTP method (usually POST for webhooks)',
      'Add an Authorization header if your endpoint requires authentication',
      'Test the connection to verify the endpoint responds correctly',
    ],
  },
];
