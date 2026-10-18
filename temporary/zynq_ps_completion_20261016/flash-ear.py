from pathlib import Path
p=Path('camera/qspi_program.cpp');s=p.read_text();s=s.replace('tx[0]=0xe9;if(!transfer(1))return 2;','''tx[0]=0xe9;if(!transfer(1))return 2;
 // W25Q256FV can retain EAR=1 after E9. Select the BootROM's low bank.
 if(!enable_write())return 4;tx[0]=0xc5;tx[1]=0;if(!transfer(2)||!idle(1))return 5;
 tx[0]=4;if(!transfer(1))return 2;tx[0]=0xc8;tx[1]=0;if(!transfer(2)||rx[1])return 7;''');p.write_bytes(s.encode())
