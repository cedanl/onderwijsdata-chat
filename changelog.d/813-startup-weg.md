### Het endpoint `/startup` is weg (#813)
- Niets riep `/startup` aan: de chart gebruikt `/health` voor de startup- en liveness-probe en `/ready` voor readiness
  (#675). Het pad gaf bovendien altijd 200, ook bij `startup_incomplete`. Een externe monitor die `/startup` aanroept,
  krijgt nu een 404; gebruik `/ready` (dezelfde twee checks, met een 503 als er één faalt) of `/health`.
