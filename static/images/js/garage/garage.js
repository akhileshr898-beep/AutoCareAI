document.addEventListener("DOMContentLoaded", () => {
    const vehicleImage =
        document.getElementById("vehicleImage");

    const rotateLeft =
        document.getElementById("rotateLeft");

    const rotateRight =
        document.getElementById("rotateRight");

    const resetVehicle =
        document.getElementById("resetVehicle");

    if (!vehicleImage) {
        return;
    }

    let rotation = 0;
    let scale = 1;

    function updateVehicle() {
        vehicleImage.style.transform =
            `rotateY(${rotation}deg) scale(${scale})`;
    }

    rotateLeft?.addEventListener("click", () => {
        rotation -= 15;
        updateVehicle();
    });

    rotateRight?.addEventListener("click", () => {
        rotation += 15;
        updateVehicle();
    });

    resetVehicle?.addEventListener("click", () => {
        rotation = 0;
        scale = 1;
        updateVehicle();
    });

    vehicleImage.addEventListener("wheel", event => {
        event.preventDefault();

        if (event.deltaY < 0) {
            scale = Math.min(scale + 0.05, 1.35);
        } else {
            scale = Math.max(scale - 0.05, 0.75);
        }

        updateVehicle();
    });
});