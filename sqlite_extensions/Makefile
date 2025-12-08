#Compile and link all shared objects by default
all: hammdist.so

#Rule used to compile and link a shared object
%.so: %.c
	$(CC) -g -fPIC -shared $< -o $@

#Rule used to remove all generated files
.PHONY: clean
clean:
	rm -rf *.so
