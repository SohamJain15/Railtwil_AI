# Delay propagation

An initial event changes only its target train. Future shared-resource overlaps are then traversed as a queue. Each dependent delay records cause train, affected train, resource, simulation time, and added wait. Propagation stops when no new dependency exists. The current overlap model is deterministic and simplified; downstream values are calculated, not stored in scenario files.
