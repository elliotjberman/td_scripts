def turn_off_cook(operator: op):
    print("turning off cook")
    operator.allowCooking = False

turn_off_cook(args[0])
