import { add, multiply } from "./lib";

function calculate(x, y) {
  const sum = add(x, y);
  const product = multiply(x, y);
  return { sum, product };
}

export class Calculator {
  run(a, b) {
    return calculate(a, b);
  }
}
