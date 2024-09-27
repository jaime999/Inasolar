
document.getElementById('origin-form').addEventListener('submit', function(event) {
  // Evita el envío del formulario
  event.preventDefault();

  // Obtén todos los campos requeridos
  const camposRequeridos = this.querySelectorAll('[required]');

  // Variable para rastrear si hay algún campo vacío
  let camposVacios = false;

  // Itera sobre los campos requeridos
  camposRequeridos.forEach(function(campo) {
    if (campo.value.trim() === '') {
      camposVacios = true;
    }
  });

  // Si no hay campos vacíos, envía el formulario
  if (!camposVacios) {
    //this.submit();
    let data = {}
    let inputs = this.getElementsByTagName("input")
    for(let input of inputs){
      data[input.name] = input.value;
    }
    
    window.electronAPI.connectOrigin(data)
  }
});

document.getElementById('destination-form').addEventListener('submit', function(event) {
  // Evita el envío del formulario
  event.preventDefault();

  // Obtén todos los campos requeridos
  const camposRequeridos = this.querySelectorAll('[required]');

  // Variable para rastrear si hay algún campo vacío
  let camposVacios = false;

  // Itera sobre los campos requeridos
  camposRequeridos.forEach(function(campo) {
    if (campo.value.trim() === '') {
      camposVacios = true;
    }
  });

  // Si no hay campos vacíos, envía el formulario
  if (!camposVacios) {
    //this.submit();
    let data = {}
    let inputs = this.getElementsByTagName("input")
    for(let input of inputs){
      data[input.name] = input.value;
    }

    window.electronAPI.connectDestination(data)
  }
});






