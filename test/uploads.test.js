const request = require('supertest');
const app = require('../src/app');

describe('uploads endpoints', () => {
  test('POST /uploads returns uploadUrl and id', async () => {
    const payload = { tenantId: 'team-a', filename: 'doc.pdf' };
    const res = await request(app).post('/uploads').set('x-dummy-user','tester@example.com').send(payload);
    expect(res.statusCode).toBe(200);
    expect(res.body).toHaveProperty('id');
    expect(res.body).toHaveProperty('uploadUrl');
    expect(res.body).toHaveProperty('expiresIn');
  });

  test('POST /uploads without required fields returns 400', async () => {
    const res = await request(app).post('/uploads').set('x-dummy-user','tester@example.com').send({});
    expect(res.statusCode).toBe(400);
    expect(res.body).toHaveProperty('error');
  });

  test('GET /files/:id/download returns downloadUrl', async () => {
    const res = await request(app).get('/files/abc123/download').set('x-dummy-user','tester@example.com');
    expect(res.statusCode).toBe(200);
    expect(res.body).toHaveProperty('downloadUrl');
    expect(res.body).toHaveProperty('expiresIn');
  });
});
