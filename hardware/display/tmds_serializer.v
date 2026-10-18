module tmds_serializer (
    input wire pixel_clk,input wire serial_clk,input wire reset,
    input wire [9:0] data,output wire positive,output wire negative
);
    wire shift1,shift2,serial;
    OSERDESE2 #(.DATA_RATE_OQ("DDR"),.DATA_RATE_TQ("SDR"),.DATA_WIDTH(10),.SERDES_MODE("MASTER"),.TRISTATE_WIDTH(1)) master (
        .OQ(serial),.CLK(serial_clk),.CLKDIV(pixel_clk),.D1(data[0]),.D2(data[1]),.D3(data[2]),.D4(data[3]),.D5(data[4]),.D6(data[5]),.D7(data[6]),.D8(data[7]),
        .OCE(1'b1),.RST(reset),.SHIFTIN1(shift1),.SHIFTIN2(shift2),.T1(1'b0),.T2(1'b0),.T3(1'b0),.T4(1'b0),.TCE(1'b0),.TBYTEIN(1'b0)
    );
    OSERDESE2 #(.DATA_RATE_OQ("DDR"),.DATA_RATE_TQ("SDR"),.DATA_WIDTH(10),.SERDES_MODE("SLAVE"),.TRISTATE_WIDTH(1)) slave (
        .SHIFTOUT1(shift1),.SHIFTOUT2(shift2),.CLK(serial_clk),.CLKDIV(pixel_clk),.D1(1'b0),.D2(1'b0),.D3(data[8]),.D4(data[9]),.D5(1'b0),.D6(1'b0),.D7(1'b0),.D8(1'b0),
        .OCE(1'b1),.RST(reset),.SHIFTIN1(1'b0),.SHIFTIN2(1'b0),.T1(1'b0),.T2(1'b0),.T3(1'b0),.T4(1'b0),.TCE(1'b0),.TBYTEIN(1'b0)
    );
    OBUFDS #(.IOSTANDARD("TMDS_33")) output_buffer(.I(serial),.O(positive),.OB(negative));
endmodule
