// Test file B for multi-file commit test

function functionB() {
    console.log("File B");
    return true;
}

class ClassB {
    constructor() {
        this.name = "Class B";
    }

    methodOne() {
        return "Method one from B";
    }
}

module.exports = { functionB, ClassB };
