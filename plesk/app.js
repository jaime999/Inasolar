const express = require('express');
const httpProxy = require('http-proxy');
const basicAuth = require('express-basic-auth')

// Crea una instancia de Express.js
const app = express();

app.use(express.static('public'));
//Habilitamos ejs
app.set('view engine', 'ejs');
// Crea un proxy que redirige las solicitudes 
const proxy_graph = httpProxy.createProxyServer({
  //target: 'http://desktop-hraj5e5',
  target: 'http://158.42.22.107',
  auth : "GEDER:GEDER"
});

//Proxy inverso a las apps de python con la autenticación HTTP
const proxy_similar = httpProxy.createProxyServer({
  //target: 'http://desktop-hraj5e5' esto si estamos en la misma red sirve,
  target: 'http://158.42.22.107:8080',
  auth : "GEDER:GEDER"
});

//Proxy inverso a las apps de python con la autenticación HTTP
const proxy_private = httpProxy.createProxyServer({
  //target: 'http://desktop-hraj5e5' esto si estamos en la misma red sirve,
  target: 'http://158.42.22.107:8050',
  auth : "GEDER:GEDER"
});

const proxy_api = httpProxy.createProxyServer({
  //target: 'http://desktop-hraj5e5' esto si estamos en la misma red sirve,
  target: 'http://158.42.22.107:8000',
});

//Autenticación par acceder desde el plesk
const protect = basicAuth({
  users: { 'GEDER': 'GEDER' },
  challenge: true
})


// Define una ruta para /grafico que redirige al backend privado
app.get('/private/grafico', protect,(req, res) => {
  proxy_graph.web(req, res);
});

// Define una ruta para /similar que redirige al backend privado
app.get('/private/similar', protect,(req, res) => {
  proxy_similar.web(req, res);
});

// Define una ruta para /private que redirige al backend privado
app.get('/private', protect,(req, res) => {
  proxy_private.web(req, res);
});

// Rutas para la api
app.get('/api/*',(req, res) => {
  proxy_api.web(req, res);
});

app.post('/api/*',(req, res) => {
  proxy_api.web(req, res);
});


app.get('/_*', (req, res) => {
  proxy_private.web(req, res);
  /*if(req.headers.referer.split('/')[4] == 'grafico'){ //grafico
    proxy_graph.web(req, res);
  } else { //similar days
    proxy_similar.web(req, res);
  }*/
});
app.get('/assets*', (req, res) => {
  proxy_private.web(req, res);
  /*if(req.headers.referer.split('/')[4] == 'grafico'){ //grafico
    proxy_graph.web(req, res);
  } else { //similar days
    proxy_similar.web(req, res);
  }*/
});

//Si actualiza los graficos
app.post('/_dash-update-component', (req, res) => {
  proxy_private.web(req, res);
  /*if(req.headers.referer.split('/')[4] == 'grafico'){ //grafico
    proxy_graph.web(req, res);
  } else { //similar days
    proxy_similar.web(req, res);
  }*/
  
});

//ZONA PRIVADA
/*app.get('/private*',protect ,(req, res) => {
  res.render('private',{
    page_name: 'private'
  });
});*/

//DESCRIPCION DEL PROYECTO
/*app.use("/proyecto",(req, res) => {
  res.render('proyecto',{
    page_name: 'proyecto'
  });
});*/

//OBJETIVOS DEL PROYECTO
app.use("/objetivos",(req, res) => {
  res.render('objetivos',{
    page_name: 'objetivos'
  });
});

app.use("/conocenos",(req, res) => {
  res.render('conocenos',{
    page_name: 'conocenos'
  });
});

app.use("/documentos",(req, res) => {
  res.render('documentos',{
    page_name: 'documentos'
  });
});

app.use("/desarrollo",(req, res) => {
  res.render('desarrollo',{
    page_name: 'desarrollo'
  });
});


//INGLES 
app.get("/en*",(req, res) => {
  //Cogemos el endpoint y cargamos la vista que tiene el mismo nombre pero con el sufijo _en
  let endpoint = req.originalUrl.split("/")[2];

  //Renderizamos la respuesta
  res.render('en/'+endpoint+'_en',{
    //Esto se usa para el nav
    page_name: endpoint
  }, (err, html) => {
      //Si el endpoint no coincide con ninguna plantilla ejs, carga el indice por defecto
      if(err){
        console.log(err)
        res.render('en/index_en',{
          page_name: 'index'
        });
      }else{
        res.send(html);
      }
    });
});

// Define una ruta predeterminada
app.use((req, res) => {
  res.render('index',{
    page_name: 'index'
  });
  //res.sendFile(__dirname + '/public/index.html');
});

// Inicia el servidor en el puerto process.env.PORT
app.listen(3000, () => {
  console.log('Servidor iniciado');
});
