const { Vonage } = require('@vonage/server-sdk');

// Initialize
const vonage = new Vonage({
  apiKey: 'aca7444b',
  apiSecret: 'dn2ZEEM2HXyOFwZI',
  applicationId: '46da75b8-4a76-42c4-acc8-201bf3cce9f0',
  privateKey: './private.key'
});

// Step 1: Create a Vonage Application (if not exists)
async function createApplication() {
  try {
    const app = await vonage.applications.createApplication({
      name: 'MyVoiceApp',
      capabilities: {
        voice: {
          webhooks: {
            answer_url: {
              address: 'https://your-webhook.com/answer',
              http_method: 'GET'
            },
            event_url: {
              address: 'https://your-webhook.com/event',
              http_method: 'POST'
            }
          }
        }
      }
    });
    console.log('Application created:', app.id);
    return app.id;
  } catch (error) {
    console.error('Error creating application:', error);
  }
}

// Step 2: Buy a virtual number (or use existing)
async function purchaseNumber(countryCode) {
  try {
    // Search for numbers
    const numbers = await vonage.number.search(countryCode, {
      features: 'VOICE',
      type: 'mobile-lvn'
    });
    
    if (numbers.length > 0) {
      const number = numbers[0];
      // Purchase the number
      await vonage.number.buy(countryCode, number.msisdn);
      console.log('Purchased number:', number.msisdn);
      return number.msisdn;
    }
  } catch (error) {
    console.error('Error purchasing number:', error);
  }
}

// Step 3: Link number to application
async function linkNumberToApp(number, appId) {
  try {
    await vonage.numbers.updateNumber({
      country: 'US',
      msisdn: number,
      appId: appId,
      moHttpUrl: 'TEST',
      voiceCallbackType: 'TEST'
    });
    console.log(`Number ${number} linked to app ${appId}`);
  } catch (error) {
    console.error('Error linking number:', error);
  }
}

// Step 4: Full setup workflow
async function setupVirtualNumber() {
  // Create application
  await linkNumberToApp('14139440806', '46da75b8-4a76-42c4-acc8-201bf3cce9f0');
}

// Execute setup
setupVirtualNumber();