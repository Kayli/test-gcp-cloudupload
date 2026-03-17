const express = require('express');

const app = express();

app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

// Serve static UI
app.use(express.static('public'));

// Routes
const uploads = require('./routes/uploads');
app.use(uploads);
const config = require('./routes/config');
app.use(config);

module.exports = app;
