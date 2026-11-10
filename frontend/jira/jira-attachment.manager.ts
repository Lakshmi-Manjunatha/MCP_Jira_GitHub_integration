
class JiraAttachmentManager {
    private selectedFiles: File[] = [];

    private input = document.querySelector<HTMLInputElement>("#attachments");
    private list = document.querySelector<HTMLElement>("#selected-attachments");

    initialize(): void {
        this.input?.addEventListener("change", () => {
            const files = Array.from(this.input?.files ?? []);

            this.selectedFiles.push(...files);

            if (this.input) this.input.value = "";

            this.render();
        });
    }

    getFiles(): File[] {
        return [...this.selectedFiles];
    }

    clear(): void {
        this.selectedFiles = [];
        if (this.input) this.input.value = "";
        this.render();
    }

    private remove(index: number): void {
        this.selectedFiles.splice(index, 1);
        this.render();
    }

    private render(): void {
        if (!this.list) return;

        this.list.replaceChildren();

        this.selectedFiles.forEach((file, index) => {
            const chip = document.createElement("span");
            chip.className = "attachment-chip";

            const filename = document.createElement("span");
            filename.textContent = file.name;

            const removeIcon = document.createElement("button");
            removeIcon.type = "button";
            removeIcon.className = "attachment-remove";
            removeIcon.textContent = "×";
            removeIcon.setAttribute("aria-label", `Remove ${file.name}`);

            removeIcon.addEventListener("click", () => {
                this.remove(index);
            });

            chip.append(filename, removeIcon);
            this.list?.appendChild(chip);
        });
    }
}
