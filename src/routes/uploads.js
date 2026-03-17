const express = require('express');
const crypto = require('crypto');

const router = express.Router();
const auth = require('../middleware/auth');

// POST /uploads - return a signed upload URL placeholder and an upload id
router.post('/uploads', auth, (req, res) => {
  const { tenantId, filename } = req.body || {};

  if (!tenantId || !filename) {
    return res.status(400).json({ error: 'tenantId and filename are required' });
  }

  const id = crypto.randomUUID();
  const uploadUrl = `https://storage.googleapis.com/fake-bucket/tenant/${encodeURIComponent(
    tenantId
  )}/files/${id}/${encodeURIComponent(filename)}?signature=placeholder`;

  // include user info in response for debugging
  res.json({ id, uploadUrl, expiresIn: 900, requestedBy: req.user && req.user.email });
});

// GET /files/:id/download - return a signed download URL placeholder
router.get('/files/:id/download', auth, (req, res) => {
  const { id } = req.params;
  if (!id) return res.status(400).json({ error: 'id required' });

  const downloadUrl = `https://storage.googleapis.com/fake-bucket/files/${id}?signature=placeholder`;
  res.json({ downloadUrl, expiresIn: 300, requestedBy: req.user && req.user.email });
});

module.exports = router;
