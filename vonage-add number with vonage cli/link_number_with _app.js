const { Vonage } = require('@vonage/server-sdk');

const vonage = new Vonage({
  apiKey: "aca7444b",
  apiSecret: "dn2ZEEM2HXyOFwZI"
});

vonage.numbers.updateNumber({
  country: "US",
  msisdn: "16626741027",
  appId: "f976ddba-bf62-42a2-8281-a6dec268ac84"
})
  .then(res => console.log(res))
  .catch(err => console.error(err));
