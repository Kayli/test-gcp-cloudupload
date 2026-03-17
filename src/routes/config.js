const express = require('express');
const router = express.Router();

router.get('/config', (req, res) => {
  const allowDev = (process.env.ALLOW_DEV_AUTH === '1') || (process.env.NODE_ENV === 'test');
  res.json({ googleClientId: process.env.GOOGLE_OAUTH_CLIENT_ID || null, allowDevAuth: allowDev });
});

module.exports = router;
