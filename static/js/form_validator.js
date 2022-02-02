const name_input = document.getElementById("name");
const description_input = document.getElementById("description");

name_input.addEventListener("input", (evt) => {
    if(name_input.validity.valid){
        name_input.style.borderColor = "green";
    } else {
        name_input.style.borderColor = "red";
    }
})

description_input.addEventListener("input", (evt) => {
    if(description_input.validity.valid) {
        description_input.style.borderColor = "green";
    } else {
        description_input.style.borderColor = "red";
    }
})