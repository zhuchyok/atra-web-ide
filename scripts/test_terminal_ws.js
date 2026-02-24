const WebSocket = require('ws');

const ws = new WebSocket('ws://localhost:8081/api/terminal/ws');

ws.on('open', function open() {
  console.log('✅ Connected to Rust Terminal WebSocket');
  // Send a simple command
  // Using \r\n for terminal line ending
  ws.send('echo "Hello from WebSocket test!"\r\n');
  
  // Wait a bit and exit
  setTimeout(() => {
    ws.send('exit\r\n');
    console.log('👋 Sent exit command');
  }, 2000);
});

ws.on('message', function message(data) {
  // Terminal output often comes in chunks, let's print it
  process.stdout.write(data.toString());
});

ws.on('error', function error(err) {
  console.error('❌ WebSocket Error:', err);
});

ws.on('close', function close() {
  console.log('\n🔌 Connection closed');
});
