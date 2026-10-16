def discounted_total(price, quantity, discount):
    subtotal = price * quantity
    return subtotal * (1 - discount)
