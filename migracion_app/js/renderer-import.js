var addRestrictionButton = document.getElementById("add-restriction-button")
var columnRestriction    = document.getElementById("column-select")
var operatorRestriction  = document.getElementById("operator-select")
var valueRestriction     = document.getElementById("value-restriction")
var listRestriction      = document.getElementById("restriction-list")
var startDatePicker      = document.getElementById("start_date")
var endDatePicker        = document.getElementById("end_date")
var removeButton         = document.getElementById("remove-button")
var backButton           = document.getElementById("back-button")
var locationSelect       = document.getElementById("location-select")
var importDataButton     = document.getElementById("import-data-button")
var coefficientInput     = document.getElementById("coefficient-input")
var areaSelect           = document.getElementById("areas-select")
var addLocationSubmit    = document.getElementById("new-location-submit")
var areaForm             = document.getElementById("area-form")
var closeLocationButton  = document.getElementById("close-location")
var scheduleButton       = document.getElementById("schedule-data-button")
var frecuencySelect      = document.getElementById("frecuency-select")
var activeRestriction    = []

//Añadir restriccion cuando se clicka el boton
addRestrictionButton.addEventListener('click', function(event) {
    event.preventDefault()
    if (valueRestriction.value != ''){
        let stringRestriction = columnRestriction.value + "\t" + operatorRestriction.value + "\t" + valueRestriction.value
        console.log(stringRestriction)
        let li  = document.createElement("li");
        li.innerHTML = stringRestriction;
        li.classList.add("list-group-item")
        li.addEventListener('click', function(event) {
            if(this.classList.toggle('active')){
                activeRestriction.push(this)
            }
        })
        listRestriction.appendChild(li);

    }
})

removeButton.addEventListener('click', function(event) {
    event.preventDefault()
    activeRestriction.forEach((element)=>{
        element.remove()
    })
})

startDatePicker.addEventListener("change", (event) => {
    updateDateRestriction("start")
})
endDatePicker.addEventListener("change", (event) => {
    updateDateRestriction("end")
})

function updateDateRestriction(source){
    if(source == "start"){
        let li = listRestriction.children[0]
        li.innerHTML = "start_date\t>=\t" + startDatePicker.value
    }else{
        let li = listRestriction.children[1]
        li.innerHTML = "end_date\t<=\t" +  endDatePicker.value

    }
}
updateDateRestriction("start")
updateDateRestriction("end")

backButton.addEventListener('click', function(event) {
    event.preventDefault()
    window.electronAPI.openSelectionWindow()
})

importDataButton.addEventListener('click', function(event) {
    let info = {}
    info.location = locationSelect.value
    //si el campo coeficiente esta vacio
    if (isNaN(parseFloat(coefficientInput.value))){
        coefficientInput.value = 1
    }
    info.coefficient = parseFloat(coefficientInput.value)
    info.restrictions = []
    for(let children of listRestriction.children){
        info.restrictions.push(children.innerHTML.replace("&gt;",">").replace("&lt;","<").replace("==","=").split("\t"))
    }
    let tr = document.getElementById('data-row').children
    info.ORIGIN_TABLE       = tr[0].innerHTML 
    info.ORIGIN_COLUMN      = tr[1].innerHTML
    info.DESTINATION_TABLE  = tr[2].innerHTML 
    info.DESTINATION_COLUMN = tr[3].innerHTML
    
    window.electronAPI.importData(info)

})

scheduleButton.addEventListener('click', function(event) {
    let info = {}
    info.location = locationSelect.value
    //si el campo coeficiente esta vacio
    if (isNaN(parseFloat(coefficientInput.value))){
        coefficientInput.value = 1
    }
    info.coefficient = parseFloat(coefficientInput.value)
    info.restrictions = []
    for(let children of listRestriction.children){
        info.restrictions.push(children.innerHTML.replace("&gt;",">").replace("&lt;","<").replace("==","=").split("\t"))
    }
    let tr = document.getElementById('data-row').children
    info.ORIGIN_TABLE       = tr[0].innerHTML 
    info.ORIGIN_COLUMN      = tr[1].innerHTML
    info.DESTINATION_TABLE  = tr[2].innerHTML 
    info.DESTINATION_COLUMN = tr[3].innerHTML

    info.frecuency = frecuencySelect.value

    window.electronAPI.scheludeDataImport(info)
})

areaForm.addEventListener('submit', function(event) {
    event.preventDefault()
    let location = {}
    location["Name"]      = document.getElementById("new-location-name").value
    location["Area"]      = areaSelect.value
    location["Type"]      = document.getElementById("type-select").value
    location["Latitude"]  = document.getElementById("latitude-input").value
    location["Longitude"] = document.getElementById("longitude-input").value
    window.electronAPI.newLocation(location)
    closeLocationButton.click()

})

areaSelect.addEventListener('change', function(event) {
    
    window.electronAPI.getCoordinates(this.options[this.selectedIndex].text)
})

