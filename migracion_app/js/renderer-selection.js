

let originSelect = document.getElementById("floatingSelectOriginTable")

originSelect.onchange = function() {
    document.getElementById("floatingSelectOriginColumn").disabled = true
    document.getElementById("addCorrelationButton").disabled = true
    window.electronAPI.getTableColumns("origin",originSelect.value)
};

let destinationSelect = document.getElementById("floatingSelectDestinationTable")

destinationSelect.onchange = function() {
    document.getElementById("floatingSelectDestinationColumn").disabled = true
    document.getElementById("addCorrelationButton").disabled = true
    window.electronAPI.getTableColumns("destination",destinationSelect.value)
};

let destinationColumnSelect = document.getElementById("floatingSelectDestinationColumn")

destinationColumnSelect.onchange = function() {
    checkDatatypes()
};

let originColumnSelect = document.getElementById("floatingSelectOriginColumn")

originColumnSelect.onchange = function() {
    checkDatatypes()
};

function checkDatatypes(){
    let destinationDatatype = document.getElementById("floatingSelectDestinationColumn").value.split(" ").slice(-1)[0]
    let originDatatype = document.getElementById("floatingSelectOriginColumn").value.split(" ").slice(-1)[0]
    let compatibleDatatypes = ['(int)','(float)','(real)']
    console.log(compatibleDatatypes.includes(originDatatype),compatibleDatatypes.includes(destinationDatatype))
    if (destinationDatatype == originDatatype){
        document.getElementById("addCorrelationButton").disabled = false
        document.getElementById("scheduleButton").disabled = false

    }else if(compatibleDatatypes.includes(originDatatype) && compatibleDatatypes.includes(destinationDatatype)){
        document.getElementById("addCorrelationButton").disabled = false
        document.getElementById("scheduleButton").disabled = false

    }else{
        document.getElementById("addCorrelationButton").disabled = true
        document.getElementById("scheduleButton").disabled = true

    }
}

let addDestinationColumnButton = document.getElementById("addDestinationColumnButton")
addDestinationColumnButton.onclick = function() {
    let hiddenInputColumn         = document.getElementById("new-column-table")
    let hiddenInputColumnSource   = document.getElementById("new-column-source")
    hiddenInputColumn.value       = destinationSelect.value
    hiddenInputColumnSource.value = 'destination'
}

let addOriginColumnButton = document.getElementById("addOriginColumnButton")
addOriginColumnButton.onclick = function() {
    let hiddenInputTableColumn    = document.getElementById("new-column-table")
    let hiddenInputColumnSource   = document.getElementById("new-column-source")

    hiddenInputTableColumn.value  = originSelect.value
    hiddenInputColumnSource.value = 'origin'

}


let addCorrelationButton = document.getElementById("addCorrelationButton")
addCorrelationButton.onclick = function() {
    let data = {
        "DESTINATION_TABLE": destinationSelect.value,
        "DESTINATION_COLUMN": document.getElementById("floatingSelectDestinationColumn").value,
        "ORIGIN_TABLE": originSelect.value,
        "ORIGIN_COLUMN": document.getElementById("floatingSelectOriginColumn").value
    }
    window.electronAPI.openImportWindow(data,false)

};

let scheduleButton = document.getElementById("scheduleButton")
scheduleButton.onclick = function() {
    let data = {
        "DESTINATION_TABLE": destinationSelect.value,
        "DESTINATION_COLUMN": document.getElementById("floatingSelectDestinationColumn").value,
        "ORIGIN_TABLE": originSelect.value,
        "ORIGIN_COLUMN": document.getElementById("floatingSelectOriginColumn").value
    }
    window.electronAPI.openImportWindow(data,true)

};

let newColumnForm = document.getElementById("add-column-form")
newColumnForm.addEventListener('submit', function(event){
    event.preventDefault()
    let newColumn = {
        "columnName":     document.getElementById("new-column-name").value,
        "columnAlternativeName": document.getElementById("new-column-alternative-name").value,
        "columnDescription": document.getElementById("new-column-description").value,
        "columnUnit" : document.getElementById("new-column-unit").value,
        "columnDatatype": document.getElementById("column-datatype-select").value,
        "columnTable":    document.getElementById("new-column-table").value,
        "columnSource":    document.getElementById("new-column-source").value
    }
    document.getElementById("close-modal-button").click()
    window.electronAPI.newColumn(newColumn)

})


