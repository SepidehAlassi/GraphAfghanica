
document.addEventListener("DOMContentLoaded", () => {
    const image = document.getElementById("detailImage");
    const viewport = document.getElementById("imageViewport");

    if (!image || !viewport) return;

    let scale = 1;
    let x = 0;
    let y = 0;
    let dragging = false;
    let startX = 0;
    let startY = 0;

    const minScale = 1;
    const maxScale = 5;

    function updateTransform() {
        image.style.transform =
            `translate(${x}px, ${y}px) scale(${scale})`;
    }

    function zoom(factor) {
        scale = Math.min(
            maxScale,
            Math.max(minScale, scale * factor)
        );

        if (scale === 1) {
            x = 0;
            y = 0;
        }

        updateTransform();
    }

    document.getElementById("zoomIn").addEventListener(
        "click", () => zoom(1.25)
    );

    document.getElementById("zoomOut").addEventListener(
        "click", () => zoom(0.8)
    );

    document.getElementById("zoomReset").addEventListener(
        "click", () => {
            scale = 1;
            x = 0;
            y = 0;
            updateTransform();
        }
    );

    viewport.addEventListener("wheel", (event) => {
        event.preventDefault();
        zoom(event.deltaY < 0 ? 1.1 : 0.9);
    }, { passive: false });

    viewport.addEventListener("pointerdown", (event) => {
        if (scale <= 1) return;

        dragging = true;
        startX = event.clientX - x;
        startY = event.clientY - y;

        viewport.setPointerCapture(event.pointerId);
        viewport.classList.add("dragging");
    });

    viewport.addEventListener("pointermove", (event) => {
        if (!dragging) return;

        x = event.clientX - startX;
        y = event.clientY - startY;

        updateTransform();
    });

    function stopDragging() {
        dragging = false;
        viewport.classList.remove("dragging");
    }

    viewport.addEventListener("pointerup", stopDragging);
    viewport.addEventListener("pointercancel", stopDragging);
});
