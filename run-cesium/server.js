/* Simple MetacatUI development server.
You'll need node.js and express.js to run this.
Install express.js with `npm install express`.
You'll also likely want to edit index.html and loader.js as needed.
See README.md for more details.
*/

const express = require("express");
const path = require("path");
const port = process.env.PORT || 3003;
const app = express();
const fs = require("fs");

app.use(express.static(__dirname));
app.listen(port);

console.log("Now running at http://localhost:" + port);