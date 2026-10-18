module video_timing (
    input wire clk, input wire reset,
    output wire active, output wire hsync, output wire vsync,
    output wire frame_start, output wire line_end,
    output reg [10:0] x=0, output reg [9:0] y=0
);
    // CEA 720p60: 74.25 MHz, 1650 x 750 total, positive sync.
    always @(posedge clk) begin
        if(reset) begin x<=0;y<=0;end
        else if(x==1649) begin x<=0;if(y==749)y<=0;else y<=y+1'b1;end
        else x<=x+1'b1;
    end
    assign active=x<1280 && y<720;
    assign hsync=x>=1390 && x<1430;
    assign vsync=y>=725 && y<730;
    assign frame_start=x==0 && y==0;
    assign line_end=x==1279;
endmodule
